#
# CLI and config file parsing.
#
import logging
import sys
import warnings
from argparse import Action, ArgumentParser
from contextlib import ExitStack
from dataclasses import MISSING
from pathlib import Path
from types import SimpleNamespace, UnionType
from typing import Optional, Sequence, Type, Union, get_origin
from unittest.mock import patch

import yaml
from tyro import cli
from tyro._argparse_formatter import TyroArgumentParser
from tyro.extras import get_parser

from .form_dict import EnvClass
from .tag import Tag
from .tag_factory import tag_factory
from .validators import not_empty

# Pydantic is not a project dependency, that is just an optional integration
try:  # Pydantic is not a dependency but integration
    from pydantic import BaseModel
    pydantic = True
except:
    pydantic = False
    BaseModel = False
try:   # Attrs is not a dependency but integration
    import attr
except:
    attr = None


WrongFields = dict[str, Tag]

eavesdrop = ""
""" Used to intercept an error message from tyro """


class Patches:
    """ Various mocking patches. """

    @staticmethod
    def custom_error(self: TyroArgumentParser, message: str):
        """ Fetch missing required options in GUI.
        On missing argument, tyro fail. We cannot determine which one was missing, except by intercepting
        the error message function. Then, we reconstruct the missing options.
        Thanks to this we will be able to invoke a UI dialog with the missing options only.
        """
        global eavesdrop
        if not message.startswith("the following arguments are required:"):
            return super(TyroArgumentParser, self).error(message)
        eavesdrop = message
        raise SystemExit(2)  # will be catched

    @staticmethod
    def custom_init(self: TyroArgumentParser, *args, **kwargs):
        super(TyroArgumentParser, self).__init__(*args, **kwargs)
        default_prefix = '-' if '-' in self.prefix_chars else self.prefix_chars[0]
        self.add_argument(default_prefix+'v', default_prefix*2+'verbose', action='count', default=0,
                          help="Verbosity level. Can be used twice to increase.")

    @staticmethod
    def custom_parse_known_args(self: TyroArgumentParser, args=None, namespace=None):
        namespace, args = super(TyroArgumentParser, self).parse_known_args(args, namespace)
        # NOTE We may check that the Env does not have its own `verbose``
        if hasattr(namespace, "verbose"):
            if namespace.verbose > 0:
                log_level = {
                    1: logging.INFO,
                    2: logging.DEBUG,
                    3: logging.NOTSET
                }.get(namespace.verbose, logging.NOTSET)
                logging.basicConfig(level=log_level, format='%(levelname)s - %(message)s')
            delattr(namespace, "verbose")
        return namespace, args


def assure_args(args: Optional[Sequence[str]] = None):
    if args is None:
        # Set env to determine whether to use sys.argv.
        # Why settings env? Prevent tyro using sys.argv if we are in an interactive shell like Jupyter,
        # as sys.argv is non-related there.
        try:
            # Note wherease `"get_ipython" in globals()` returns True in Jupyter, it is still False
            # in a script a Jupyter cell runs. Hence we must put here this lengthty statement.
            global get_ipython
            get_ipython()
        except:
            args = sys.argv[1:]  # Fetch from the CLI
        else:
            args = []
    return args


def run_tyro_parser(env_class: Type[EnvClass] | list[Type[EnvClass]],
                    kwargs: dict,
                    add_verbosity: bool,
                    ask_for_missing: bool,
                    args: Optional[Sequence[str]] = None) -> tuple[EnvClass, WrongFields]:
    type_form = env_class
    if isinstance(type_form, list):
        # We have to convert the list of possible classes (subcommands) to union for tyro.
        # We have to accept the list and not an union directly because we are not able
        # to type hint a union type, only a union instance.
        # def sugg(a: UnionType[EnvClass]) -> EnvClass: ...
        # sugg(Subcommand1 | Subcommand2). -> IDE will not suggest anything
        type_form = Union[tuple(type_form)]  # Union[*type_form] not supported in Python3.10
        env_classes = env_class
    else:
        env_classes = [env_class]

    parser: ArgumentParser = get_parser(type_form, **kwargs)

    # Mock parser, inject special options into
    patches = []
    if ask_for_missing:  # Get the missing flags from the parser
        patches.append(patch.object(TyroArgumentParser, 'error', Patches.custom_error))
    if add_verbosity:  # Mock parser to add verbosity
        # The verbose flag is added only if neither the env_class nor any of the subcommands have the verbose flag already
        if all("verbose" not in cl.__annotations__ for cl in env_classes):
            patches.extend((
                patch.object(TyroArgumentParser, '__init__', Patches.custom_init),
                patch.object(TyroArgumentParser, 'parse_known_args', Patches.custom_parse_known_args)
            ))

    # Run the parser, with the mocks
    try:
        with ExitStack() as stack:
            [stack.enter_context(p) for p in patches]  # apply just the chosen mocks
            return cli(type_form, args=args, **kwargs), {}
    except BaseException as e:
        if ask_for_missing and getattr(e, "code", None) == 2 and eavesdrop:
            # Some required arguments are missing. Determine which.
            wf = {}
            for arg in eavesdrop.partition(":")[2].strip().split(", "):
                treat_missing(type_form, kwargs, parser, wf, arg)

            # Second attempt to parse CLI
            # Why catching warnings? All the meaningful warnings
            # have been produces during the first attempt.
            # Now, when we defaulted all the missing fields with None,
            # tyro produces 'UserWarning: The field (...) but the default value has type <class 'str'>.'
            # (This is not true anymore; to support pydantic we put a default value of the type,
            # so there is probably no more warning to be caught.)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                return cli(type_form, args=args, **kwargs), wf
        raise


# NOTE We should implement
# ./program.py -> fails with tyro now
# ./program.py subcommand1 -> fails with tyro now
# @dataclass
# class SharedArgs:
#     foo: int
# @dataclass
# class Subcommand1(SharedArgs):
#     a: int = 1
# @dataclass
# class Subcommand2(SharedArgs):
#     b: int
# subcommand = run(Subcommand1 | Subcommand2)
def treat_missing(env_class, kwargs: dict, parser: ArgumentParser, wf: dict, arg: str):
    if arg.startswith("{"):
        # missing subcommand not implemented
        return
    try:
        argument: Action = next(iter(p for p in parser._actions if arg in p.option_strings))
    except:
        # missing subcommand flag not implemented
        return
    argument.default = "DEFAULT"  # NOTE I do not know whether used
    if "." in argument.dest:
        # missing nested required argument handler not implemented, we let the CLI fail
        # (with a graceful message from tyro)
        return
    else:
        # get the original attribute name (argparse uses dash instead of underscores)
        field_name = argument.dest
        if field_name not in env_class.__annotations__:
            field_name = field_name.replace("-", "_")
        if field_name not in env_class.__annotations__:
            raise ValueError(f"Cannot find {field_name} in the configuration object")

            # NOTE: We put '' to the UI to clearly state that the value is missing.
            # However, the UI then is not able to use the number filtering capabilities.
        tag = wf[field_name] = tag_factory("",
                                           argument.help.replace("(required)", ""),
                                           validation=not_empty,
                                           _src_class=env_class,
                                           _src_key=field_name
                                           )
        # Why `type_()`? We need to put a default value so that the parsing will not fail.
        # A None would be enough because Mininterface will ask for the missing values
        # promply, however, Pydantic model would fail.
        setattr(kwargs["default"], field_name, tag.annotation())


def _parse_cli(env_class: Type[EnvClass] | list[Type[EnvClass]],
               config_file: Path | None = None,
               add_verbosity=True,
               ask_for_missing=True,
               args=None,
               **kwargs) -> tuple[EnvClass | None, dict, WrongFields]:
    """ Parse CLI arguments, possibly merged from a config file.

    Args:
        env_class: Class with the configuration.
        config_file: File to load YAML to be merged with the configuration.
            You do not have to re-define all the settings in the config file, you can choose a few.
    Kwargs:
        The same as for argparse.ArgumentParser.

    Returns:
        Configuration namespace.
    """
    # Load config file
    if config_file and isinstance(env_class, list):
        # NOTE. Reading config files when using subcommands is not implemented.
        static = {}
        kwargs["default"] = None
        warnings.warn(f"Config file {config_file} is ignored because subcommands are used."
                      "It is not easy to set who this should work. "
                      "Describe the developer your usecase so that they might implement this.")
    if "default" not in kwargs and not isinstance(env_class, list):
        # Undocumented feature. User put a namespace into kwargs["default"]
        # that already serves for defaults. We do not fetch defaults yet from a config file.
        disk = {}
        if config_file:
            disk = yaml.safe_load(config_file.read_text()) or {}  # empty file is ok
            # Nested dataclasses have to be properly initialized. YAML gave them as dicts only.
            for key in (key for key, val in disk.items() if isinstance(val, dict)):
                disk[key] = env_class.__annotations__[key](**disk[key])

        # Fill default fields
        if pydantic and issubclass(env_class, BaseModel):
            # Unfortunately, pydantic needs to fill the default with the actual values,
            # the default value takes the precedence over the hard coded one, even if missing.
            static = {key: env_class.model_fields.get(key).default
                      for key in env_class.__annotations__ if not key.startswith("__") and not key in disk}
        elif attr and attr.has(env_class):
            # Unfortunately, attrs needs to fill the default with the actual values,
            # the default value takes the precedence over the hard coded one, even if missing.
            static = {key: field.default
                      for key, field in attr.fields_dict(env_class).items() if not key.startswith("__") and not key in disk}
        else:
            # To ensure the configuration file does not need to contain all keys, we have to fill in the missing ones.
            # Otherwise, tyro will spawn warnings about missing fields.
            static = {key: getattr(env_class, key, MISSING)
                      for key in env_class.__annotations__ if not key.startswith("__") and not key in disk}
        kwargs["default"] = SimpleNamespace(**(disk | static))

    # Load configuration from CLI
    env, wrong_fields = run_tyro_parser(env_class, kwargs, add_verbosity, ask_for_missing, args)
    return env, wrong_fields
