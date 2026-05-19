from itertools import product
from utils import classes_overlap
from preferences import score_timetable

def group_rows_by_course_and_index(rows: list[dict]) -> dict:
    """
    Converts flat parsed rows into:
    
    {
        "MH3500": [
            {
                "course": "MH3500",
                "course_name": "STATISTICS",
                "index": "70605",
                "classes": [...]
            }
        ]
    }
    """
    grouped = {}

    for row in rows:
        course = row["course"]
        index = row["index"]

        if course not in grouped:
            grouped[course] = {}

        if index not in grouped[course]:
            grouped[course][index] = {
                "course": course,
                "course_name": row["course_name"],
                "au": row["au"],
                "index": index,
                "classes": [],
            }

        class_info = {
            "type": row["type"],
            "group": row["group"],
            "day": row["day"],
            "start": row["start"],
            "end": row["end"],
            "venue": row["venue"],
            "remark": row["remark"],
        }

        grouped[course][index]["classes"].append(class_info)

    # Convert inner dictionaries into lists
    result = {}

    for course, indexes in grouped.items():
        result[course] = list(indexes.values())

    return result

# clash detection functions

def flatten_classes(index_combination: tuple[dict, ...]) -> list[dict]:
    """
    Takes a combination of selected indexes and returns all class sessions.
    """
    all_classes = []

    for course_index in index_combination:
        for class_session in course_index["classes"]:
            class_with_course = {
                **class_session,
                "course": course_index["course"],
                "course_name": course_index["course_name"],
                "index": course_index["index"],
            }
            all_classes.append(class_with_course)

    return all_classes


def find_clashes(classes: list[dict]) -> list[tuple[dict, dict]]:
    """
    Finds all clashes inside a list of class sessions.
    """
    clashes = []

    for i in range(len(classes)):
        for j in range(i + 1, len(classes)):
            if classes_overlap(classes[i], classes[j]):
                clashes.append((classes[i], classes[j]))

    return clashes


def has_clash(classes: list[dict]) -> bool:
    """
    Returns True if any pair of classes clash.
    """
    return len(find_clashes(classes)) > 0


# main timetable generation function

def generate_clash_free_timetables(grouped_courses: dict) -> list[dict]:
    """
    Generates all possible one-index-per-course combinations
    and keeps only clash-free timetables.
    """
    course_codes = list(grouped_courses.keys())
    all_index_options = [grouped_courses[course] for course in course_codes]

    valid_timetables = []

    for combination in product(*all_index_options):
        classes = flatten_classes(combination)

        clashes = find_clashes(classes)

        if clashes:
            continue

        selected_indexes = {
            course_index["course"]: course_index["index"]
            for course_index in combination
        }

        valid_timetables.append(
            {
                "selected_indexes": selected_indexes,
                "classes": classes,
            }
        )

    return valid_timetables

# timetable ranking functions

def rank_timetables(valid_timetables: list[dict], preferences: dict) -> list[dict]:
    """
    Adds preference score to each valid timetable and sorts them.

    Lower score = better timetable.
    """
    ranked = []

    for timetable in valid_timetables:
        score, explanations, breakdown = score_timetable(
            timetable["classes"],
            preferences,
        )

        ranked.append(
            {
                **timetable,
                "score": score,
                "score_breakdown": breakdown,
                "explanations": explanations,
            }
        )

    ranked.sort(key=lambda timetable: timetable["score"])

    return ranked