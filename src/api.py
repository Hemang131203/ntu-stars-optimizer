from pathlib import Path
import json
import tempfile
import sys

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Allow this API file to import other files from the src folder
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.append(str(CURRENT_DIR))

from pdf_parser import parse_pdf_to_rows
from optimizer import (
    group_rows_by_course_and_index,
    find_top_timetables_fast,
)
from preferences import prepare_preferences_for_scoring


MAX_PDFS = 8
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_COMBINATIONS = 2_000_000
SEARCH_TIME_LIMIT_SECONDS = 25
MAX_VALID_TIMETABLES_TO_SCORE = 300_000


app = FastAPI(title="NTU STARS Timetable Optimizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # okay for local testing; restrict this after deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "NTU STARS Timetable Optimizer API is running",
    }


def validate_preferences(preferences_json: str) -> dict:
    """
    Validates and parses preferences JSON from the frontend.
    """
    try:
        preferences = json.loads(preferences_json)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid preferences format. Please check your preference settings.",
        )

    if not isinstance(preferences, dict):
        raise HTTPException(
            status_code=400,
            detail="Preferences must be a JSON object.",
        )

    return preferences


def validate_uploaded_files(files: list[UploadFile]) -> None:
    """
    Validates number of PDFs and file type.
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Please upload at least one PDF.",
        )

    if len(files) > MAX_PDFS:
        raise HTTPException(
            status_code=400,
            detail=f"You uploaded {len(files)} PDFs. Please upload at most {MAX_PDFS} PDFs.",
        )

    for uploaded_file in files:
        filename = uploaded_file.filename or ""

        if not filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"{filename} is not a PDF file. Please upload only PDF files.",
            )


def estimate_combination_count(grouped_courses: dict) -> int:
    """
    Estimates total possible timetable combinations by multiplying
    the number of index options for each detected course.
    """
    total = 1

    for index_options in grouped_courses.values():
        total *= len(index_options)

    return total


def build_detected_courses_summary(grouped_courses: dict) -> list[dict]:
    """
    Builds a clean summary of detected courses for the frontend.
    """
    detected_courses = []

    for course, index_options in grouped_courses.items():
        detected_courses.append(
            {
                "course": course,
                "course_name": index_options[0]["course_name"]
                if index_options
                else "UNKNOWN",
                "indexes_found": len(index_options),
            }
        )

    return detected_courses


@app.post("/optimize")
async def optimize_timetable(
    files: list[UploadFile] = File(...),
    preferences_json: str = Form(...),
):
    """
    Accepts any number of PDF files and preferences JSON.
    Returns top ranked clash-free timetables.
    """

    validate_uploaded_files(files)
    preferences = validate_preferences(preferences_json)

    all_rows = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for uploaded_file in files:
            filename = uploaded_file.filename or "uploaded.pdf"
            pdf_path = temp_path / filename

            total_size = 0

            with open(pdf_path, "wb") as buffer:
                while True:
                    chunk = await uploaded_file.read(1024 * 1024)

                    if not chunk:
                        break

                    total_size += len(chunk)

                    if total_size > MAX_FILE_SIZE_BYTES:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"{filename} is too large. "
                                f"Maximum file size is {MAX_FILE_SIZE_MB} MB."
                            ),
                        )

                    buffer.write(chunk)

            try:
                rows = parse_pdf_to_rows(str(pdf_path))
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Could not parse {filename}. "
                        "Please make sure it is a valid NTU class schedule PDF."
                    ),
                )

            all_rows.extend(rows)

    if not all_rows:
        raise HTTPException(
            status_code=400,
            detail=(
                "No class schedule rows were extracted. "
                "Please check that the uploaded PDFs are NTU class schedule PDFs."
            ),
        )

    grouped_courses = group_rows_by_course_and_index(all_rows)

    if not grouped_courses:
        raise HTTPException(
            status_code=400,
            detail="No courses were detected from the uploaded PDFs.",
        )

    estimated_combinations = estimate_combination_count(grouped_courses)

    if estimated_combinations > MAX_COMBINATIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The uploaded modules create {estimated_combinations:,} possible combinations, "
                f"which is above the current limit of {MAX_COMBINATIONS:,}. "
                "Try reducing the number of uploaded modules or add more filtering later."
            ),
        )

    prepared_preferences = prepare_preferences_for_scoring(preferences)
    search_result = find_top_timetables_fast(
        grouped_courses=grouped_courses,
        preferences=prepared_preferences,
        top_k=5,
        time_limit_seconds=SEARCH_TIME_LIMIT_SECONDS,
        max_valid_timetables=MAX_VALID_TIMETABLES_TO_SCORE,
    )

    valid_timetables_found = search_result["valid_timetables_found"]
    top_timetables = search_result["top_timetables"]
    search_truncated = search_result["search_truncated"]
    truncation_reason = search_result["truncation_reason"]
    elapsed_seconds = search_result["elapsed_seconds"]

    if not top_timetables:
        if search_truncated:
            if truncation_reason == "time_limit":
                message = (
                    "Search stopped because it exceeded the server time limit. "
                    "Try fewer modules or stricter preferences."
                )
            else:
                message = (
                    "Search stopped because the number of valid timetables is very large. "
                    "Try fewer modules or stricter preferences."
                )
        else:
            message = (
                "No clash-free timetable was found for the uploaded modules. "
                "This may mean every possible index combination has at least one clash."
            )

        return {
            "detected_courses": build_detected_courses_summary(grouped_courses),
            "total_rows_extracted": len(all_rows),
            "estimated_combinations": estimated_combinations,
            "valid_timetables_found": valid_timetables_found,
            "top_timetables": [],
            "search_truncated": search_truncated,
            "truncation_reason": truncation_reason,
            "optimization_elapsed_seconds": elapsed_seconds,
            "message": message,
        }

    if search_truncated:
        if truncation_reason == "time_limit":
            message = (
                "Timetables generated from a partial search due to server time limit. "
                "Best options found so far are shown."
            )
        else:
            message = (
                "Timetables generated from a partial search due to very large result space. "
                "Best options found so far are shown."
            )
    else:
        message = "Timetables generated successfully."

    return {
        "detected_courses": build_detected_courses_summary(grouped_courses),
        "total_rows_extracted": len(all_rows),
        "estimated_combinations": estimated_combinations,
        "valid_timetables_found": valid_timetables_found,
        "top_timetables": top_timetables,
        "search_truncated": search_truncated,
        "truncation_reason": truncation_reason,
        "optimization_elapsed_seconds": elapsed_seconds,
        "message": message,
    }
