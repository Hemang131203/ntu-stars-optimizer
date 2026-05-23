import heapq
from itertools import product
from time import perf_counter
from utils import classes_overlap
from preferences import score_timetable, score_timetable_fast
from utils import time_to_minutes

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


def strip_internal_fields(classes: list[dict]) -> list[dict]:
    """
    Removes internal scoring/clash keys before returning API payloads.
    """
    cleaned = []
    for class_session in classes:
        cleaned.append(
            {
                key: value
                for key, value in class_session.items()
                if not key.startswith("_")
            }
        )

    return cleaned


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


def prepare_index_option(index_option: dict, option_id: int) -> dict:
    """
    Adds metadata for faster clash checks and scoring.
    """
    prepared_classes = []

    for class_session in index_option["classes"]:
        prepared_classes.append(
            {
                **class_session,
                "course": index_option["course"],
                "course_name": index_option["course_name"],
                "index": index_option["index"],
                "_start_minutes": time_to_minutes(class_session["start"]),
                "_end_minutes": time_to_minutes(class_session["end"]),
            }
        )

    return {
        **index_option,
        "_id": option_id,
        "classes": prepared_classes,
    }


def options_conflict(option_a: dict, option_b: dict) -> bool:
    """
    Returns True if any class from option_a clashes with option_b.
    """
    for class_a in option_a["classes"]:
        a_day = class_a["day"]
        a_start = class_a["_start_minutes"]
        a_end = class_a["_end_minutes"]

        for class_b in option_b["classes"]:
            if a_day != class_b["day"]:
                continue

            b_start = class_b["_start_minutes"]
            b_end = class_b["_end_minutes"]

            if a_start < b_end and b_start < a_end:
                return True

    return False


def find_top_timetables_fast(
    grouped_courses: dict,
    preferences: dict,
    top_k: int = 5,
    time_limit_seconds: float | None = None,
    max_valid_timetables: int | None = None,
) -> dict:
    """
    Fast timetable search:
    - Precomputes pairwise index conflicts
    - Uses DFS with pruning instead of flattening every product combination
    - Keeps only top_k timetables in a heap
    """
    if not grouped_courses:
        return {
            "valid_timetables_found": 0,
            "top_timetables": [],
            "search_truncated": False,
            "truncation_reason": None,
            "elapsed_seconds": 0.0,
        }

    option_id_counter = 0
    prepared_course_options = []
    option_lookup: dict[int, dict] = {}

    for course_options in grouped_courses.values():
        prepared_options = []

        for option in course_options:
            prepared_option = prepare_index_option(option, option_id_counter)
            prepared_options.append(prepared_option)
            option_lookup[option_id_counter] = prepared_option
            option_id_counter += 1

        prepared_course_options.append(prepared_options)

    # Fewer options first -> stronger pruning earlier
    prepared_course_options.sort(key=len)

    conflict_map = {
        option_id: set()
        for option_id in option_lookup
    }

    for i in range(len(prepared_course_options)):
        for j in range(i + 1, len(prepared_course_options)):
            for option_a in prepared_course_options[i]:
                for option_b in prepared_course_options[j]:
                    if options_conflict(option_a, option_b):
                        conflict_map[option_a["_id"]].add(option_b["_id"])
                        conflict_map[option_b["_id"]].add(option_a["_id"])

    valid_timetable_count = 0
    search_truncated = False
    truncation_reason = None
    states_visited = 0
    best_heap = []
    insertion_order = 0

    selected_option_ids: list[int] = []
    selected_classes: list[dict] = []
    selected_indexes: dict[str, str] = {}

    start_time = perf_counter()

    def should_stop_search() -> bool:
        nonlocal search_truncated
        nonlocal truncation_reason

        if search_truncated:
            return True

        if (
            time_limit_seconds is not None
            and perf_counter() - start_time >= time_limit_seconds
        ):
            search_truncated = True
            truncation_reason = "time_limit"
            return True

        return False

    def maybe_store_top_candidate(score: int) -> None:
        nonlocal insertion_order

        candidate = {
            "score": score,
            "selected_indexes": dict(selected_indexes),
            "option_ids": tuple(selected_option_ids),
        }

        heap_entry = (-score, insertion_order, candidate)
        insertion_order += 1

        if len(best_heap) < top_k:
            heapq.heappush(best_heap, heap_entry)
            return

        worst_score_in_heap = -best_heap[0][0]
        if score < worst_score_in_heap:
            heapq.heapreplace(best_heap, heap_entry)

    def dfs(course_index: int) -> None:
        nonlocal valid_timetable_count
        nonlocal states_visited
        nonlocal search_truncated
        nonlocal truncation_reason

        if search_truncated:
            return

        states_visited += 1
        if should_stop_search():
            return

        if course_index == len(prepared_course_options):
            if max_valid_timetables is not None and valid_timetable_count >= max_valid_timetables:
                search_truncated = True
                truncation_reason = "max_valid_timetables"
                return

            valid_timetable_count += 1
            score = score_timetable_fast(selected_classes, preferences)
            maybe_store_top_candidate(score)
            return

        for candidate_option in prepared_course_options[course_index]:
            if should_stop_search():
                return

            candidate_id = candidate_option["_id"]
            conflicts = conflict_map[candidate_id]

            if any(selected_id in conflicts for selected_id in selected_option_ids):
                continue

            selected_option_ids.append(candidate_id)
            selected_indexes[candidate_option["course"]] = candidate_option["index"]
            selected_classes.extend(candidate_option["classes"])

            dfs(course_index + 1)

            del selected_indexes[candidate_option["course"]]
            del selected_classes[-len(candidate_option["classes"]):]
            selected_option_ids.pop()

    dfs(0)

    elapsed_seconds = perf_counter() - start_time

    ranked_candidates = [
        entry[2]
        for entry in sorted(best_heap, key=lambda entry: (-entry[0], entry[1]))
    ]

    top_timetables = []

    for candidate in ranked_candidates:
        classes_with_internal_fields = []
        for option_id in candidate["option_ids"]:
            classes_with_internal_fields.extend(option_lookup[option_id]["classes"])

        score, explanations, breakdown = score_timetable(
            classes_with_internal_fields,
            preferences,
        )

        top_timetables.append(
            {
                "selected_indexes": candidate["selected_indexes"],
                "classes": strip_internal_fields(classes_with_internal_fields),
                "score": score,
                "score_breakdown": breakdown,
                "explanations": explanations,
            }
        )

    return {
        "valid_timetables_found": valid_timetable_count,
        "top_timetables": top_timetables,
        "search_truncated": search_truncated,
        "truncation_reason": truncation_reason,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }

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
