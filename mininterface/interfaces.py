# Access to interfaces via this module assures lazy loading
from code import interact
from dataclasses import replace
from importlib import import_module
from os import isatty
import sys
from typing import Literal, Optional, Type

from .mininterface import EnvClass, Mininterface
from .settings import MininterfaceSettings, InterfaceName
from .exceptions import InterfaceNotAvailable

InterfaceType = Type[Mininterface] | InterfaceName | None


def _load(name, mod, attr):
    try:
        globals()[name] = getattr(import_module(mod, __name__), attr)
        return globals()[name]
    except InterfaceNotAvailable:
        return None


def __getattr__(name):
    match name:
        # shortcuts
        case "GuiInterface":
            return __getattr__("TkInterface")
        case "TuiInterface":
            # if textual not installed or isatty False, return TextInterface
            if sys.stdin.isatty():
                try:
                    return __getattr__("TextualInterface")
                except ImportError:
                    pass
            return __getattr__("TextInterface")

        # real interfaces
        case "TkInterface":
            return _load(name, "..tk_interface", "TkInterface")
        case "TextualInterface":
            return _load(name, "..textual_interface", "TextualInterface")
        case "TextInterface":
            return _load(name, "..text_interface", "TextInterface")
        case "WebInterface":
            return _load(name, "..web_interface", "WebInterface")
        case _:
            return None  # such attribute does not exist


def _choose_settings(type_: Mininterface, settings: Optional[MininterfaceSettings]):
    """ Pass only the relevant settings section suitable for the given interface type """
    opt = None
    if settings:
        match type_.__name__:
            case "TkInterface":
                opt = settings.gui
            case "TextualInterface":
                opt = settings.textual
            case "TextInterface":
                opt = settings.text
            case "WebInterface":
                opt = settings.web
    return opt


def _get_interface_type(interface: InterfaceType = None):
    match interface:
        case "gui" | None:
            return __getattr__("GuiInterface")
        case "text":
            return __getattr__("TextInterface")
        case "web":
            return __getattr__("WebInterface")
        case "tui" | "textual":
            return __getattr__("TuiInterface")
        case _:
            raise InterfaceNotAvailable


def get_interface(interface: InterfaceType = None, title="", settings: Optional[MininterfaceSettings] = None, env: EnvClass = None) -> Mininterface[EnvClass]:
    """ Returns the best available interface.

    Similar to [mininterface.run][mininterface.run] but without CLI or config file parsing.

    Args:
        interface: An interface type of preference.
        title:
        settings: [MininterfaceSettings][mininterface.settings.MininterfaceSettings] objects
        env: You can specify the .env attribute of the returned object.
    """
    def call(type_):
        opt = _choose_settings(type_, settings)
        return type_(title, opt, env)

    interface = interface or (settings.interface if settings else None)

    try:
        if isinstance(interface, type) and issubclass(interface, Mininterface):
            return call(interface)
        return call(_get_interface_type(interface))
    except InterfaceNotAvailable:
        pass
    try:  # try a default TUI
        if interface not in ("text", "textual", "tui"):
            return call(_get_interface_type("tui"))
    except InterfaceNotAvailable:
        # Even though TUI is able to claim a non-interactive terminal,
        # ex. when doing a cron job, a terminal cannot be made interactive.
        pass
    return call(Mininterface)


__all__ = ["GuiInterface", "TuiInterface", "TkInterface", "TextualInterface", "TextInterface"]
