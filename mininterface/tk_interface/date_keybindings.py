from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from date_entry import DateEntry


    def bind_all_events(widget: "DateEntry") -> None:
        """Bind all events to the main window widget"""
        # Copy to clipboard with ctrl+c
        widget.bind_all("<Control-c>", widget.copy_to_clipboard)

        # Select all in the spinbox with ctrl+a
        widget.bind_all("<Control-a>", lambda event: widget.select_all())

        # Paste from clipboard with ctrl+v
        widget.bind_all("<Control-v>", lambda event: widget.paste_from_clipboard())

        # Toggle calendar widget with ctrl+shift+c
        widget.bind_all("<Control-Shift-C>", lambda event: widget.toggle_calendar())

    def bind_spinbox_events(widget: "DateEntry") -> None:
        """Bind events to the spinbox widget"""

        # Bind up/down arrow keys
        widget.spinbox.bind("<Up>", widget.increment_value)
        widget.spinbox.bind("<Down>", widget.decrement_value)

        # Bind mouse click on spinbox arrows
        widget.spinbox.bind("<ButtonRelease-1>", widget.on_spinbox_click)

        # Bind key release event to update calendar when user changes the input field
        widget.spinbox.bind("<KeyRelease>", widget.on_spinbox_change)
