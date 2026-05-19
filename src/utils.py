def time_to_minutes(time_str: str) -> int:
    """
    Converts '13:30' into minutes from midnight.
    """
    hour, minute = map(int, time_str.split(":"))
    return hour * 60 + minute


def classes_overlap(class_a: dict, class_b: dict) -> bool:
    """
    Returns True if two classes overlap in time on the same day.

    Back-to-back classes are NOT considered clashes.
    Example:
    13:30-15:30 and 15:30-17:30 = no clash
    """
    if class_a["day"] != class_b["day"]:
        return False

    a_start = time_to_minutes(class_a["start"])
    a_end = time_to_minutes(class_a["end"])
    b_start = time_to_minutes(class_b["start"])
    b_end = time_to_minutes(class_b["end"])

    return a_start < b_end and b_start < a_end