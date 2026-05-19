from pathlib import Path
import json
from pdf_parser import parse_pdf_to_rows
from optimizer import (
    group_rows_by_course_and_index,
    generate_clash_free_timetables,
    rank_timetables,
)
from preferences import load_preferences


# Display functions

DAY_ORDER = {
    "MON": 1,
    "TUE": 2,
    "WED": 3,
    "THU": 4,
    "FRI": 5,
    "SAT": 6,
    "SUN": 7,
}


def sort_classes_for_display(classes: list[dict]) -> list[dict]:
    return sorted(
        classes,
        key=lambda c: (DAY_ORDER.get(c["day"], 99), c["start"], c["end"]),
    )


def print_timetable(timetable: dict, rank: int) -> None:
    print("=" * 80)
    print(f"Rank {rank} | Score: {timetable['score']}")
    print("Score breakdown:")
    for category, value in timetable.get("score_breakdown", {}).items():
        print(f"- {category}: {value}")
    print("=" * 80)

    print("\nSelected indexes:")
    for course, index in timetable["selected_indexes"].items():
        print(f"- {course}: {index}")

    print("\nWeekly timetable:")

    sorted_classes = sort_classes_for_display(timetable["classes"])

    current_day = None

    for c in sorted_classes:
        if c["day"] != current_day:
            current_day = c["day"]
            print(f"\n{current_day}:")

        print(
            f'  {c["start"]}-{c["end"]} | '
            f'{c["course"]} {c["index"]} | '
            f'{c["type"]} {c["group"]} | '
            f'{c["venue"]}'
        )

    print("\nPreference notes:")

    if timetable["explanations"]:
        for note in timetable["explanations"][:8]:
            print(f"- {note}")
    else:
        print("- No preference penalties.")

    print()



# Main execution flow


def main():
    pdf_folder = Path("data/sample_pdfs")
    output_folder = Path("outputs")
    output_folder.mkdir(exist_ok=True)

    pdf_files = list(pdf_folder.glob("*.pdf"))

    if not pdf_files:
        print("No PDF files found in data/sample_pdfs")
        return

    print(f"Found {len(pdf_files)} PDF file(s):")

    all_rows = []

    for pdf_file in pdf_files:
        print(f"- Parsing {pdf_file.name}")

        rows = parse_pdf_to_rows(str(pdf_file))
        all_rows.extend(rows)

        detected_courses = sorted(set(row["course"] for row in rows))
        detected_indexes = sorted(set(row["index"] for row in rows))

        print(f"  Detected course(s): {detected_courses}")
        print(f"  Rows extracted: {len(rows)}")
        print(f"  Indexes found: {len(detected_indexes)}")

    rows_output_path = output_folder / "parsed_rows.json"

    with open(rows_output_path, "w", encoding="utf-8") as file:
        json.dump(all_rows, file, indent=2)

    grouped_courses = group_rows_by_course_and_index(all_rows)

    grouped_output_path = output_folder / "grouped_courses.json"

    with open(grouped_output_path, "w", encoding="utf-8") as file:
        json.dump(grouped_courses, file, indent=2)

    print("\nDone.")
    print(f"Total rows extracted: {len(all_rows)}")
    print(f"Saved flat rows to: {rows_output_path}")
    print(f"Saved grouped courses to: {grouped_output_path}")

    print("\nDetected course summary:")

    for course, index_options in grouped_courses.items():
        course_name = index_options[0]["course_name"] if index_options else "UNKNOWN"
        print(f"- {course} {course_name}: {len(index_options)} indexes")

    print("\nGenerating clash-free timetables...")

    valid_timetables = generate_clash_free_timetables(grouped_courses)

    valid_output_path = output_folder / "valid_timetables.json"

    with open(valid_output_path, "w", encoding="utf-8") as file:
        json.dump(valid_timetables[:50], file, indent=2)

    print("\nRanking timetables based on preferences...")

    preferences = load_preferences()
    print("\nLoaded preferences:")
    print(json.dumps(preferences, indent=2))

    ranked_timetables = rank_timetables(valid_timetables, preferences)

    ranked_output_path = output_folder / "ranked_timetables.json"

    with open(ranked_output_path, "w", encoding="utf-8") as file:
        json.dump(ranked_timetables[:50], file, indent=2)

    print(f"Valid clash-free timetables found: {len(valid_timetables)}")
    print(f"Saved first 50 valid timetables to: {valid_output_path}")
    print(f"Saved first 50 ranked timetables to: {ranked_output_path}")

    if ranked_timetables:
        print("\nTop 5 recommended timetables:")

        for rank, timetable in enumerate(ranked_timetables[:5], start=1):
            print_timetable(timetable, rank)
    else:
        print("No clash-free timetable found.")


if __name__ == "__main__":
    main()