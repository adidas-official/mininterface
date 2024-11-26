import tkinter as tk
import re
from datetime import datetime
from date_helpers import find_valid_date, find_valid_time, get_part_index
from date_keybindings import bind_all_events, bind_spinbox_events
from date_widgets import create_calendar, create_widgets

try:
    from tkcalendar import Calendar
except ImportError:
    Calendar = None

class DateEntry(tk.Frame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.pack(expand=True, fill=tk.BOTH)
        bind_all_events(self)
        create_widgets(self)

    def toggle_calendar(self, event=None):
        if Calendar:
            if hasattr(self, 'frame') and self.frame.winfo_ismapped():
                self.frame.pack_forget()
            else:
                self.frame.pack(padx=20, pady=20, expand=True, fill=tk.BOTH)

    def increment_value(self, event=None):
        self.change_date(1)

    def decrement_value(self, event=None):
        self.change_date(-1)

    def change_date(self, delta):
        date_str = self.spinbox.get()
        caret_pos = self.spinbox.index(tk.INSERT)

        date = find_valid_date(self.spinbox.get())
        time = find_valid_time(self.spinbox.get())  

        if date:
            split_input = re.split(r'[- :.]', date_str)

            # Get the caret position to determine which part of the date to change, returns an index of the part
            # if time is not in the input, the index will always be 2 (day) to change day by default
            # < 5 = year
            # < 8 = month
            # < 11 = day
            # < 14 = hour
            # < 17 = minute
            # < 20 = second
            # >= 20 = millisecond
            part_index = get_part_index(caret_pos, len(split_input))

            # Increment or decrement the relevant part
            number = int(split_input[part_index])
            new_number = number + delta
            split_input[part_index] = str(new_number).zfill(len(split_input[part_index]))

            if time:
                new_value_str = f"{split_input[0]}-{split_input[1]}-{split_input[2]} {split_input[3]}:{split_input[4]}:{split_input[5]}.{split_input[6][:2]}"
                string_format = '%Y-%m-%d %H:%M:%S.%f'
            else:
                new_value_str = f"{split_input[0]}-{split_input[1]}-{split_input[2]}"
                string_format = '%Y-%m-%d'

            # Validate the new date
            try:
                datetime.strptime(new_value_str, string_format)
                self.spinbox.delete(0, tk.END)
                self.spinbox.insert(0, new_value_str)
                self.spinbox.icursor(caret_pos)
                if Calendar:
                    self.update_calendar(new_value_str, string_format)
            except ValueError:
                pass

    def on_spinbox_click(self, event):
        # Check if the click was on the spinbox arrows
        if self.spinbox.identify(event.x, event.y) == "buttonup":
            self.increment_value()
        elif self.spinbox.identify(event.x, event.y) == "buttondown":
            self.decrement_value()

    def on_date_select(self, event):
        selected_date = self.calendar.selection_get()
        self.spinbox.delete(0, tk.END)
        self.spinbox.insert(0, selected_date.strftime('%Y-%m-%d'))
        self.spinbox.icursor(len(self.spinbox.get()))

    def on_spinbox_change(self, event):
        if Calendar:
            self.update_calendar(self.spinbox.get())

    def update_calendar(self, date_str, string_format='%Y-%m-%d'):
        try:
            date = datetime.strptime(date_str, string_format)
            self.calendar.selection_set(date)
        except ValueError:
            pass

    def copy_to_clipboard(self, event=None):
        self.clipboard_clear()
        self.clipboard_append(self.spinbox.get())
        self.update()  # now it stays on the clipboard after the window is closed
        self.show_popup("Copied to clipboard")

    def show_popup(self, message):
        popup = tk.Toplevel(self)
        popup.wm_title("")

        label = tk.Label(popup, text=message, font=("Arial", 12))
        label.pack(side="top", fill="x", pady=10, padx=10)

        # Position the popup window in the top-left corner of the widget
        x = self.winfo_rootx()
        y = self.winfo_rooty()
        
        # Position of the popup window has to be "inside" the main window or it will be focused on popup
        popup.geometry(f"400x100+{x+200}+{y-150}")

        # Close the popup after 2 seconds
        self.after(1000, popup.destroy)

        # Keep focus on the spinbox
        self.spinbox.focus_force()


    def select_all(self, event=None):
        self.spinbox.selection_range(0, tk.END)
        self.spinbox.focus_set()
        self.spinbox.icursor(0)
        return 'break'

    def paste_from_clipboard(self, event=None):
        self.spinbox.delete(0, tk.END)
        self.spinbox.insert(0, self.clipboard_get())

if __name__ == "__main__":
    root = tk.Tk()
    # Get the screen width and height
    # This is calculating the position of the TOTAL dimentions of all screens combined
    # How to calculate the position of the window on the current screen?
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Calculate the position to center the window
    x = (screen_width // 2) - 400
    y = (screen_height // 2) - 600

    # Set the position of the window
    root.geometry(f"800x600+{x}+{y}")
    # keep the main widget on top all the time
    root.wm_attributes("-topmost", False)
    root.wm_attributes("-topmost", True)
    root.title("Date Editor")

    date_entry = DateEntry(root)
    date_entry.pack(expand=True, fill=tk.BOTH)
    root.mainloop()

