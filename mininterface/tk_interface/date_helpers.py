import re

def find_valid_date(input):
    # use regex to find the date part
    date_part = re.search(r'\d{4}-\d{2}-\d{2}', input)
    if date_part:
        return date_part.group()
    return False

def find_valid_time(input):
    # use regex to find the time part
    time_part = re.search(r'\d{2}:\d{2}:\d{2}', input)
    if time_part:
        return time_part.group()
    return False

def get_part_index(caret_pos, split_length):
    if caret_pos < 5:       # year
        return 0
    elif caret_pos < 8:     # month
        return 1
    elif caret_pos < 11:    # day
        return 2
    elif split_length > 3:
        if caret_pos < 14:  # hour
            return 3
        elif caret_pos < 17: # minute
            return 4
        elif caret_pos < 20: # second
            return 5
        else:               # millisecond
            return 6
    return 2