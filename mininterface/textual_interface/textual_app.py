from typing import TYPE_CHECKING
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import (Checkbox, Footer, Header, Input, Label,
                             RadioButton, RadioSet)

from ..auxiliary import flatten
from ..common import Cancelled
from ..form_dict import TagDict, formdict_to_widgetdict
from ..tag import Tag

if TYPE_CHECKING:
    from .. import TextualInterface

# NOTE: For a metaclass conflict I was not able to inherit from BackendAdaptor
class TextualApp(App[bool | None]):

    BINDINGS = [
        ("up", "go_up", "Go up"),
        ("down", "go_up", "Go down"),
        # Form confirmation
        # * ctrl/alt+enter does not work
        # * enter without priority is consumed by input fields
        # * enter with priority is not shown in the footer
        Binding("enter", "confirm", "Ok", show=True, priority=True),
        Binding("Enter", "confirm", "Ok"),
        ("escape", "exit", "Cancel"),
    ]

    def __init__(self, interface: "TextualInterface"):
        super().__init__()
        self.facet = interface.facet
        self.title = self.facet._title
        self.widgets = None
        self.focused_i: int = 0
        self.interface = interface

    @staticmethod
    def widgetize(tag: Tag) -> Checkbox | Input:
        """ Wrap Tag to a textual widget. """
        v = tag._get_ui_val()
        if tag.annotation is bool or not tag.annotation and (v is True or v is False):
            o = Checkbox(tag.name or "", v)
        elif tag._get_choices():
            o = RadioSet(*(RadioButton(label, value=val == tag.val) for label, val in tag._get_choices().items()))
        else:
            if not isinstance(v, (float, int, str, bool)):
                v = str(v)
            o = Input(str(v), placeholder=tag.name or "")
        o._link = tag  # The Textual widgets need to get back to this value
        return o

    # Why class method? I do not know how to re-create the dialog if needed.
    @classmethod
    def run_dialog(cls, window: "TextualApp", form: TagDict, title: str = "") -> TagDict:
        if title:
            window.title = title

        # NOTE Sections (~ nested dicts) are not implemented, they flatten.
        # Maybe just 'flatten' might be removed.
        widgets: list[Checkbox | Input] = [f for f in flatten(formdict_to_widgetdict(form, cls.widgetize))]
        window.widgets = widgets

        if not window.run():
            raise Cancelled

        # validate and store the UI value → Tag value → original value
        candidates = ((
            field._link,
            str(field.pressed_button.label) if isinstance(field, RadioSet) else field.value
        ) for field in widgets)
        if not Tag._submit_values(candidates):
            return cls.run_dialog(TextualApp(window.interface), form, title)
        return form

    def compose(self) -> ComposeResult:
        if self.title:
            yield Header()
        yield Footer()
        if text := self.interface._redirected.join():
            yield Label(text, id="buffered_text")
        with VerticalScroll():
            for fieldt in self.widgets:
                if isinstance(fieldt, Input):
                    yield Label(fieldt.placeholder)
                yield fieldt
                yield Label(fieldt._link.description)
                yield Label("")

    def on_mount(self):
        self.widgets[self.focused_i].focus()

    def action_confirm(self):
        # next time, start on the same widget
        # NOTE the functionality is probably not used
        self.focused_i = next((i for i, inp in enumerate(self.widgets) if inp == self.focused), None)
        self.exit(True)

    def action_exit(self):
        self.exit()

    def on_key(self, event: events.Key) -> None:
        try:
            index = self.widgets.index(self.focused)
        except ValueError:  # probably some other element were focused
            return
        match event.key:
            case "down":
                self.widgets[(index + 1) % len(self.widgets)].focus()
            case "up":
                self.widgets[(index - 1) % len(self.widgets)].focus()
            case letter if len(letter) == 1:  # navigate by letters
                for inp_ in self.widgets[index+1:] + self.widgets[:index]:
                    label = inp_.label if isinstance(inp_, Checkbox) else inp_.placeholder
                    if str(label).casefold().startswith(letter):
                        inp_.focus()
                        break