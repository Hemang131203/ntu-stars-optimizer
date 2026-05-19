from pathlib import Path
import re
import pdfplumber


DAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts all text from a PDF file using pdfplumber.
    Returns the extracted text as one string.
    """
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    all_text = []

    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            all_text.append(f"\n--- PAGE {page_number} ---\n{text}")

    return "\n".join(all_text)


def format_time(raw_time: str) -> tuple[str, str]:
    """
    Converts '0930-1120' into ('09:30', '11:20').
    """
    start_raw, end_raw = raw_time.split("-")

    start = f"{start_raw[:2]}:{start_raw[2:]}"
    end = f"{end_raw[:2]}:{end_raw[2:]}"

    return start, end


def clean_course_name(raw_name: str) -> str:
    """
    Cleans course name by removing symbols such as *, ~, ^, # near the AU part.
    """
    return raw_name.strip().replace("*", "").replace("~", "").replace("^", "").replace("#", "")


def extract_course_info(text: str) -> tuple[str, str, float | None]:
    """
    Extracts course code, course name, and AU from the PDF text.

    Example:
    MH3500 STATISTICS*~ 4.0 AU
    becomes:
    ('MH3500', 'STATISTICS', 4.0)
    """
    course_pattern = re.compile(
        r"\b([A-Z]{2}\d{4})\s+(.+?)\s+(\d+(?:\.\d+)?)\s+AU\b"
    )

    match = course_pattern.search(text)

    if not match:
        return "UNKNOWN", "UNKNOWN", None

    course_code = match.group(1)
    course_name = clean_course_name(match.group(2))
    au = float(match.group(3))

    return course_code, course_name, au


def is_table_noise(line: str) -> bool:
    """
    Removes lines that are not actual class schedule rows.
    """
    line = line.strip()

    if not line:
        return True

    noise_starts = [
        "--- PAGE",
        "Class Schedule",
        "Search Result",
        "Prerequisite:",
        "INDEX TYPE GROUP DAY TIME VENUE REMARK",
        "https://",
        "* Course is available",
        "~ Course is available",
        "^ Self",
        "# Course is available",
    ]

    return any(line.startswith(prefix) for prefix in noise_starts)


def parse_class_line(
    line: str,
    course_code: str,
    course_name: str,
    au: float | None,
    current_index: str | None,
) -> tuple[dict | None, str | None]:
    """
    Parses one schedule line.

    Handles both formats:

    70605 LEC/STUDIO LE FRI 1130-1320 LKC-LT
    LEC/STUDIO LE MON 1230-1320 LT26

    The second row uses the previous index.
    """
    original_line = line
    line = line.strip()

    if is_table_noise(line):
        return None, current_index

    tokens = line.split()

    if len(tokens) < 5:
        return None, current_index

    index = current_index

    # If line starts with a 5-digit index, use it and remove it from tokens
    if re.fullmatch(r"\d{5}", tokens[0]):
        index = tokens[0]
        tokens = tokens[1:]

    if index is None:
        return None, current_index

    # Find the day token. This is more reliable than assuming fixed positions.
    day_position = None

    for i, token in enumerate(tokens):
        if token in DAYS:
            day_position = i
            break

    if day_position is None:
        return None, index

    # Need: type, group, day, time
    if day_position < 2:
        return None, index

    class_type = " ".join(tokens[: day_position - 1])
    group = tokens[day_position - 1]
    day = tokens[day_position]

    if day_position + 1 >= len(tokens):
        return None, index

    time_raw = tokens[day_position + 1]

    if not re.fullmatch(r"\d{4}-\d{4}", time_raw):
        return None, index

    start, end = format_time(time_raw)

    remaining = tokens[day_position + 2:]

    venue_parts = []
    remark_parts = []

    # Split venue and remark when "Teaching" appears
    if "Teaching" in remaining:
        teaching_index = remaining.index("Teaching")
        venue_parts = remaining[:teaching_index]
        remark_parts = remaining[teaching_index:]
    else:
        venue_parts = remaining

    venue = " ".join(venue_parts).strip()
    remark = " ".join(remark_parts).strip()

    row = {
        "course": course_code,
        "course_name": course_name,
        "au": au,
        "index": index,
        "type": class_type,
        "group": group,
        "day": day,
        "start": start,
        "end": end,
        "venue": venue,
        "remark": remark,
        "raw_line": original_line,
    }

    return row, index


def parse_pdf_to_rows(pdf_path: str) -> list[dict]:
    """
    Extracts structured class rows from one PDF.
    """
    text = extract_text_from_pdf(pdf_path)
    course_code, course_name, au = extract_course_info(text)

    rows = []
    current_index = None

    for line in text.splitlines():
        row, current_index = parse_class_line(
            line=line,
            course_code=course_code,
            course_name=course_name,
            au=au,
            current_index=current_index,
        )

        if row:
            rows.append(row)

    return rows