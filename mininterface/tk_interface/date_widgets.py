from tkinter import Frame, BOTH, Spinbox
from datetime import datetime
from date_keybindings import bind_spinbox_events

try:
    from tkcalendar import Calendar
except ImportError:
    Calendar = None

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from date_entry import DateEntry


def create_widgets(widget: "DateEntry") -> None:
    widget.spinbox = Spinbox(widget, font=("Arial", 16), width=30, wrap=True)
    widget.spinbox.pack(padx=20, pady=20)
    widget.spinbox.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-4])
    widget.spinbox.focus_set()
    widget.spinbox.icursor(8)

    bind_spinbox_events(widget)

    if Calendar:
        create_calendar(widget)

def create_calendar(widget: "DateEntry") -> None:
    # Create a frame to hold the calendar
    widget.frame = Frame(widget)
    widget.frame.pack(padx=20, pady=20, expand=True, fill=BOTH)

    # Add a calendar widget
    widget.calendar = Calendar(widget.frame, selectmode='day', date_pattern='yyyy-mm-dd')
    widget.calendar.place(relwidth=0.7, relheight=0.8, anchor='n', relx=0.5)

    # Bind date selection event
    widget.calendar.bind("<<CalendarSelected>>", widget.on_date_select)

    # Initialize calendar with the current date
    widget.update_calendar(widget.spinbox.get(), '%Y-%m-%d %H:%M:%S.%f')

def toggle_calendar(widget: "DateEntry", event=None) -> None:
    if Calendar:
        if hasattr(widget, 'frame') and widget.frame.winfo_ismapped():
            widget.frame.pack_forget()
        else:
            widget.frame.pack(padx=20, pady=20, expand=True, fill=BOTH)