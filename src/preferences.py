from utils import time_to_minutes
import json
from pathlib import Path


FLEXIBLE_CLASS_TYPES = {"TUT", "LAB", "SEM", "PRAC", "PRACTICAL"}


def is_flexible_class(class_session: dict) -> bool:
    """
    Preferences apply mainly to tutorials/labs/etc.
    Lectures are ignored by preference scoring by default.
    """
    class_type = class_session["type"].upper()

    for flexible_type in FLEXIBLE_CLASS_TYPES:
        if flexible_type in class_type:
            return True

    return False


def get_default_preferences() -> dict:
    """
    Default preferences for testing.
    Later, these will come from the user's UI inputs.
    """
    return {
        "avoid_before_time": "10:00",
        "avoid_after_time": "17:00",
        "avoid_days": ["FRI"],
        "prefer_fewer_school_days": True,
        "prefer_shorter_gaps": True,
        "minimum_gap_minutes": 10,
    }

def load_preferences(preferences_path: str = "data/preferences.json") -> dict:
    """
    Loads user preferences from a JSON file.
    If the file does not exist, uses default preferences.
    """
    path = Path(preferences_path)

    if not path.exists():
        print(f"Preferences file not found: {preferences_path}")
        print("Using default preferences.")
        return get_default_preferences()

    with open(path, "r", encoding="utf-8") as file:
        preferences = json.load(file)

    return preferences


def score_timetable(classes: list[dict], preferences: dict) -> tuple[int, list[str], dict]:
    """
    Scores a timetable based on user preferences.

    Lower score = better timetable.

    Returns:
    score, explanations, breakdown
    """
    explanations = []

    breakdown = {
        "early_late_day_penalty": 0,
        "avoid_time_window_penalty": 0,
        "school_days_penalty": 0,
        "gap_penalty": 0,
    }

    breakdown["early_late_day_penalty"] = score_flexible_class_time_preferences(
        classes, preferences, explanations
    )

    breakdown["avoid_time_window_penalty"] = score_avoid_time_windows(
        classes, preferences, explanations
    )

    breakdown["school_days_penalty"] = score_school_days(
        classes, preferences, explanations
    )

    breakdown["gap_penalty"] = score_gaps(
        classes, preferences, explanations
    )

    total_score = sum(breakdown.values())

    return total_score, explanations, breakdown


def score_flexible_class_time_preferences(
    classes: list[dict],
    preferences: dict,
    explanations: list[str],
) -> int:
    """
    Scores preferences that apply only to tutorials/labs/etc.
    """
    score = 0

    avoid_before_time = preferences.get("avoid_before_time")
    avoid_after_time = preferences.get("avoid_after_time")
    avoid_days = preferences.get("avoid_days", [])

    avoid_before_minutes = (
        time_to_minutes(avoid_before_time) if avoid_before_time else None
    )
    avoid_after_minutes = time_to_minutes(avoid_after_time) if avoid_after_time else None

    for c in classes:
        if not is_flexible_class(c):
            continue

        start = time_to_minutes(c["start"])
        end = time_to_minutes(c["end"])

        class_label = (
            f'{c["course"]} {c["index"]} {c["type"]} {c["group"]} '
            f'{c["day"]} {c["start"]}-{c["end"]}'
        )

        if avoid_before_minutes is not None and start < avoid_before_minutes:
            score += 40
            explanations.append(f"Avoid early class: {class_label}")

        if avoid_after_minutes is not None and end > avoid_after_minutes:
            score += 40
            explanations.append(f"Avoid late class: {class_label}")

        if c["day"] in avoid_days:
            score += 50
            explanations.append(f"Avoid selected day: {class_label}")

    return score


def score_school_days(
    classes: list[dict],
    preferences: dict,
    explanations: list[str],
) -> int:
    """
    Adds penalty for each school day used.
    This uses all classes, including lectures, because lectures still affect timetable days.
    """
    if not preferences.get("prefer_fewer_school_days", False):
        return 0

    days = {c["day"] for c in classes}

    # Small penalty per school day
    penalty = len(days) * 10

    explanations.append(f"School days used: {len(days)}")

    return penalty


def score_gaps(
    classes: list[dict],
    preferences: dict,
    explanations: list[str],
) -> int:
    """
    Scores gaps between classes on the same day.

    - Prefer shorter gaps.
    - Penalize gaps below minimum_gap_minutes.
    """
    score = 0

    prefer_shorter_gaps = preferences.get("prefer_shorter_gaps", False)
    minimum_gap_minutes = preferences.get("minimum_gap_minutes", 0)

    classes_by_day = {}

    for c in classes:
        classes_by_day.setdefault(c["day"], []).append(c)

    for day, day_classes in classes_by_day.items():
        sorted_classes = sorted(day_classes, key=lambda c: time_to_minutes(c["start"]))

        for i in range(len(sorted_classes) - 1):
            current_class = sorted_classes[i]
            next_class = sorted_classes[i + 1]

            current_end = time_to_minutes(current_class["end"])
            next_start = time_to_minutes(next_class["start"])

            gap = next_start - current_end

            # There should not be negative gaps because clashes were removed.
            if gap < 0:
                continue

            if minimum_gap_minutes and gap < minimum_gap_minutes:
                score += 25
                explanations.append(
                    f"{day} gap below preferred minimum: "
                    f"{gap} min between "
                    f'{current_class["course"]} {current_class["type"]} and '
                    f'{next_class["course"]} {next_class["type"]}'
                )

            if prefer_shorter_gaps:
                # Every 30 minutes of gap adds 1 point.
                score += gap // 30

    return score

# New scoring function for avoid time windows

def score_avoid_time_windows(
    classes: list[dict],
    preferences: dict,
    explanations: list[str],
) -> int:
    """
    Penalizes tutorials/labs/etc. that overlap with user-defined avoid time windows.

    Example:
    MON avoid 12:30-14:00
    TUE avoid 15:00-16:00

    Lectures are ignored by default.
    """
    score = 0
    avoid_time_windows = preferences.get("avoid_time_windows", [])

    for window in avoid_time_windows:
        window_day = window["day"]
        window_start = time_to_minutes(window["start"])
        window_end = time_to_minutes(window["end"])

        for c in classes:
            if not is_flexible_class(c):
                continue

            if c["day"] != window_day:
                continue

            class_start = time_to_minutes(c["start"])
            class_end = time_to_minutes(c["end"])

            overlaps = class_start < window_end and window_start < class_end

            if overlaps:
                score += 60

                explanations.append(
                    f"Avoid time window: {c['course']} {c['index']} "
                    f"{c['type']} {c['group']} {c['day']} "
                    f"{c['start']}-{c['end']} overlaps "
                    f"{window_day} {window['start']}-{window['end']}"
                )

    return score