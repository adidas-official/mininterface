# Starting and maintaining a program, using mininterface, in the system.
import sys
from collections import defaultdict
from dataclasses import is_dataclass
from pathlib import Path
from subprocess import run
from typing import TYPE_CHECKING, Type
from warnings import warn

from .cli_parser import run_tyro_parser
from .common import Command, InterfaceNotAvailable
from .experimental import SubmitButton
from .form_dict import EnvClass, TagDict, dataclass_to_tagdict
from .mininterface import Mininterface
from .tag import Tag
from .text_interface import TextInterface

# Import optional interfaces
try:
    from .tk_interface import TkInterface
except ImportError:
    if TYPE_CHECKING:
        pass  # Replace TYPE_CHECKING with `type GuiInterface = None` since Python 3.12
    else:
        TkInterface = None
try:
    from .textual_interface import TextualInterface
except ImportError:
    TextualInterface = None

GuiInterface = TkInterface
TuiInterface = TextualInterface or TextInterface


class Start:
    def __init__(self, title="", interface: Type[Mininterface] | str | None = None):
        self.title = title
        self.interface = interface

    def get_interface(self, env=None):
        interface = self.interface
        try:
            if interface == "tui":  # undocumented feature
                interface = TuiInterface
            elif interface == "gui":  # undocumented feature
                interface = GuiInterface
            if interface is None:
                raise InterfaceNotAvailable  # GuiInterface might be None when import fails
            else:
                interface = interface(self.title, env)
        except InterfaceNotAvailable:  # Fallback to a different interface
            interface = TuiInterface(self.title, env)
        return interface

    def integrate(self, env=None):
        """ Integrate to the system

        Bash completion uses argparse.prog, so do not set prog="Program Name" as bash completion would stop working.

        NOTE: This is a basic and bash only integration. It might be easily expanded.
        """
        m = self.get_interface()
        comp_dir = Path("/etc/bash_completion.d/")
        prog = Path(sys.argv[0]).name
        target = comp_dir/prog

        if comp_dir.exists():
            if target.exists():
                m.alert(f"Destination {target} already exists. Exit.")
                return
            if m.is_yes(f"We generate the bash completion into {target}"):
                run(["sudo", "-E", sys.argv[0], "--tyro-write-completion", "bash", target])
                m.alert(f"Integration completed. Start a bash session to see whether bash completion is working.")
                return

        m.alert("Cannot auto-detect. Use --tyro-print-completion {bash/zsh/tcsh} to get the sh completion script.")

    def choose_subcommand(self, env_classes: list[Type[EnvClass]]):
        m = self.get_interface()
        forms: TagDict = defaultdict(Tag)

        # Subcommands might be inherited from the same base class, they might have some common fields
        # that has meaning for all subcommands (like `--output-filename`).
        # In the current implementation, common fields works only if all of the classes have the same base.
        # It does not implement nested fields.
        common_bases = set.intersection(*(set(c for c in cl.__mro__ if is_dataclass(c)) for cl in env_classes))
        common_fields = [field for cl in common_bases for field in cl.__annotations__]

        for env_class in env_classes:
            form, wf = run_tyro_parser(env_class, {}, False, True, args=[])  # NOTE what to do with wf?
            name = form.__class__.__name__
            tags = dataclass_to_tagdict(form)

            # Pull out common fields to the common level
            for cf in common_fields:
                local = tags[""].pop(cf)
                forms[cf]._fetch_from(local)._src_obj_add(local)

            if isinstance(form, Command):
                # add the button to submit just that one dataclass, by calling its Command.run
                tags[""][name] = Tag(lambda form=form: form.run())
            else:
                warn(f"Subcommand dataclass {name} does not inherit from the Command."
                     " It is not known what should happen with it, it is being neglected from the CLI subcommands."
                     " Describe the developer your usecase so that they might implement this.")
                tags[""][name] = Tag("disabled", description=f"Subcommand {name} does not inherit from the Command."
                                     " Hence it is disabled.")

            forms[name] = tags

        m.form(forms, submit=False)
        # TODO test, docs
