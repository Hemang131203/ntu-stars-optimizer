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


def prepare_preferences_for_scoring(preferences: dict) -> dict:
    """
    Adds cached/normalized fields so repeated timetable scoring is faster.
    """
    prepared = dict(preferences)

    avoid_before_time = prepared.get("avoid_before_time")
    avoid_after_time = prepared.get("avoid_after_time")
    avoid_days = prepared.get("avoid_days", [])

    try:
        prepared["_avoid_before_minutes"] = (
            time_to_minutes(avoid_before_time) if avoid_before_time else None
        )
    except (TypeError, ValueError):
        prepared["_avoid_before_minutes"] = None

    try:
        prepared["_avoid_after_minutes"] = (
            time_to_minutes(avoid_after_time) if avoid_after_time else None
        )
    except (TypeError, ValueError):
        prepared["_avoid_after_minutes"] = None
    prepared["_avoid_days_set"] = set(avoid_days)

    prepared_windows = []
    for window in prepared.get("avoid_time_windows", []):
        day = window.get("day")
        start = window.get("start")
        end = window.get("end")

        if not day or not start or not end:
            continue

        try:
            start_minutes = time_to_minutes(start)
            end_minutes = time_to_minutes(end)
        except (TypeError, ValueError):
            continue

        prepared_windows.append(
            {
                "day": day,
                "start": start,
                "end": end,
                "start_minutes": start_minutes,
                "end_minutes": end_minutes,
            }
        )

    prepared["_avoid_time_windows_prepared"] = prepared_windows
    prepared["_is_prepared_for_scoring"] = True

    return prepared


def ensure_prepared_preferences(preferences: dict) -> dict:
    if preferences.get("_is_prepared_for_scoring"):
        return preferences

    return prepare_preferences_for_scoring(preferences)


def class_start_minutes(class_session: dict) -> int:
    cached = class_session.get("_start_minutes")
    if cached is not None:
        return cached

    return time_to_minutes(class_session["start"])


def class_end_minutes(class_session: dict) -> int:
    cached = class_session.get("_end_minutes")
    if cached is not None:
        return cached

    return time_to_minutes(class_session["end"])


def score_timetable(classes: list[dict], preferences: dict) -> tuple[int, list[str], dict]:
    """
    Scores a timetable based on user preferences.

    Lower score = better timetable.

    Returns:
    score, explanations, breakdown
    """
    prepared_preferences = ensure_prepared_preferences(preferences)
    explanations: list[str] = []

    breakdown = {
        "early_late_day_penalty": 0,
        "avoid_time_window_penalty": 0,
        "school_days_penalty": 0,
        "gap_penalty": 0,
    }

    breakdown["early_late_day_penalty"] = score_flexible_class_time_preferences(
        classes, prepared_preferences, explanations
    )

    breakdown["avoid_time_window_penalty"] = score_avoid_time_windows(
        classes, prepared_preferences, explanations
    )

    breakdown["school_days_penalty"] = score_school_days(
        classes, prepared_preferences, explanations
    )

    breakdown["gap_penalty"] = score_gaps(
        classes, prepared_preferences, explanations
    )

    total_score = sum(breakdown.values())

    return total_score, explanations, breakdown


def score_timetable_fast(classes: list[dict], preferences: dict) -> int:
    """
    Fast path used during large search:
    returns total score only (no explanations/breakdown).
    """
    prepared_preferences = ensure_prepared_preferences(preferences)

    total_score = 0
    total_score += score_flexible_class_time_preferences(
        classes,
        prepared_preferences,
        explanations=None,
    )
    total_score += score_avoid_time_windows(
        classes,
        prepared_preferences,
        explanations=None,
    )
    total_score += score_school_days(
        classes,
        prepared_preferences,
        explanations=None,
    )
    total_score += score_gaps(
        classes,
        prepared_preferences,
        explanations=None,
    )

    return total_score


def score_flexible_class_time_preferences(
    classes: list[dict],
    preferences: dict,
    explanations: list[str] | None,
) -> int:
    """
    Scores preferences that apply only to tutorials/labs/etc.
    """
    score = 0

    avoid_before_minutes = preferences.get("_avoid_before_minutes")
    avoid_after_minutes = preferences.get("_avoid_after_minutes")
    avoid_days = preferences.get("_avoid_days_set", set())

    for c in classes:
        if not is_flexible_class(c):
            continue

        start = class_start_minutes(c)
        end = class_end_minutes(c)

        class_label = (
            f'{c["course"]} {c["index"]} {c["type"]} {c["group"]} '
            f'{c["day"]} {c["start"]}-{c["end"]}'
        )

        if avoid_before_minutes is not None and start < avoid_before_minutes:
            score += 40
            if explanations is not None:
                explanations.append(f"Avoid early class: {class_label}")

        if avoid_after_minutes is not None and end > avoid_after_minutes:
            score += 40
            if explanations is not None:
                explanations.append(f"Avoid late class: {class_label}")

        if c["day"] in avoid_days:
            score += 50
            if explanations is not None:
                explanations.append(f"Avoid selected day: {class_label}")

    return score


def score_school_days(
    classes: list[dict],
    preferences: dict,
    explanations: list[str] | None,
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

    if explanations is not None:
        explanations.append(f"School days used: {len(days)}")

    return penalty


def score_gaps(
    classes: list[dict],
    preferences: dict,
    explanations: list[str] | None,
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
        sorted_classes = sorted(day_classes, key=class_start_minutes)

        for i in range(len(sorted_classes) - 1):
            current_class = sorted_classes[i]
            next_class = sorted_classes[i + 1]

            current_end = class_end_minutes(current_class)
            next_start = class_start_minutes(next_class)

            gap = next_start - current_end

            # There should not be negative gaps because clashes were removed.
            if gap < 0:
                continue

            if minimum_gap_minutes and gap < minimum_gap_minutes:
                score += 25
                if explanations is not None:
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
    explanations: list[str] | None,
) -> int:
    """
    Penalizes tutorials/labs/etc. that overlap with user-defined avoid time windows.

    Example:
    MON avoid 12:30-14:00
    TUE avoid 15:00-16:00

    Lectures are ignored by default.
    """
    score = 0
    avoid_time_windows = preferences.get("_avoid_time_windows_prepared", [])

    for window in avoid_time_windows:
        window_day = window["day"]
        window_start = window["start_minutes"]
        window_end = window["end_minutes"]

        for c in classes:
            if not is_flexible_class(c):
                continue

            if c["day"] != window_day:
                continue

            class_start = class_start_minutes(c)
            class_end = class_end_minutes(c)

            overlaps = class_start < window_end and window_start < class_end

            if overlaps:
                score += 60

                if explanations is not None:
                    explanations.append(
                        f"Avoid time window: {c['course']} {c['index']} "
                        f"{c['type']} {c['group']} {c['day']} "
                        f"{c['start']}-{c['end']} overlaps "
                        f"{window_day} {window['start']}-{window['end']}"
                    )

    return score
