# NTU STARS Timetable Optimizer

A Python-based timetable optimizer for NTU students.

This project helps students find clash-free course index combinations from NTU class schedule PDFs. It parses uploaded class schedule PDFs, extracts course indexes and lesson timings, checks for timetable clashes, and ranks valid timetables based on user-defined preferences.

## Live Demo

https://ntu-stars-optimizer.netlify.app/

## Features

- Upload/use multiple NTU class schedule PDFs
- Extract course codes, index numbers, lesson types, days, times, venues, and remarks
- Group lessons by course and index
- Generate all possible one-index-per-course timetable combinations
- Remove timetables with class timing clashes
- Rank clash-free timetables using user preferences
- Support preferences such as:
  - Avoid tutorials/labs before a selected time
  - Avoid tutorials/labs after a selected time
  - Avoid tutorials/labs on selected days
  - Avoid custom time windows
  - Prefer fewer school days
  - Prefer shorter gaps
  - Minimum preferred gap between classes
- Lectures are treated as anchor sessions:
  - Lectures are checked for clashes
  - Lectures are ignored by preference scoring by default

## Project Flow

```text
User downloads one class schedule PDF per module
↓
PDFs are placed inside data/sample_pdfs
↓
Parser extracts class timing rows
↓
Rows are grouped by course and index
↓
Optimizer generates all possible index combinations
↓
Combinations with clashes are removed
↓
Remaining timetables are scored using preferences
↓
Top recommended timetables are displayed
Project Structure
ntu-stars-optimizer/
│
├── data/
│   ├── sample_pdfs/
│   │   └── PDF files go here
│   └── preferences.json
│
├── outputs/
│   ├── parsed_rows.json
│   ├── grouped_courses.json
│   ├── valid_timetables.json
│   └── ranked_timetables.json
│
├── src/
│   ├── main.py
│   ├── pdf_parser.py
│   ├── optimizer.py
│   ├── preferences.py
│   ├── utils.py
│   └── models.py
│
├── requirements.txt
└── README.md
Setup

Create and activate a virtual environment:

python -m venv venv

On Windows PowerShell:

.\venv\Scripts\Activate.ps1

Install dependencies:

pip install -r requirements.txt
Usage

Place NTU class schedule PDFs inside:

data/sample_pdfs

Edit preferences in:

data/preferences.json

Run the program:

python src/main.py
Example Preferences
{
  "avoid_before_time": "10:00",
  "avoid_after_time": "17:00",
  "avoid_days": ["FRI"],
  "prefer_fewer_school_days": true,
  "prefer_shorter_gaps": true,
  "minimum_gap_minutes": 10,
  "avoid_time_windows": [
    {
      "day": "MON",
      "start": "12:30",
      "end": "14:00"
    },
    {
      "day": "TUE",
      "start": "15:00",
      "end": "16:00"
    }
  ]
}
Clash Logic

Two classes clash only if their timings overlap on the same day.

Back-to-back classes are allowed.

Example:

13:30-15:30
15:30-17:30

This is not a clash.

The overlap condition is:

class_a_start < class_b_end
AND
class_b_start < class_a_end
Preference Logic

The only mandatory rule is:

No class timing clashes

All other preferences affect ranking only.

Lectures are included in clash checking but ignored by preference scoring by default.

This means if a user blocks Monday 12:30-14:00, a lecture in that window is acceptable, but a tutorial or lab in that window receives a penalty.

Current Status

This is currently a Python prototype. A future version can be converted into a web application where users upload PDFs and select preferences through a UI.


## Step 2: Check `requirements.txt`

Make sure `requirements.txt` contains only this for now:

```text
pdfplumber
pandas

pandas is not heavily used yet, but it is fine to keep because we may use it later for CSV/export.

Step 3: Add .gitignore

Create a new file in the main project folder:

.gitignore

Paste this:

venv/
__pycache__/
*.pyc
outputs/*.json
.DS_Store
.env

This prevents unnecessary files from being committed later.

Step 4: Check final structure

Your project should now look like:

NTU-STARS-OPTIMIZER
├── data
│   ├── preferences.json
│   └── sample_pdfs
├── outputs
├── src
│   ├── main.py
│   ├── models.py
│   ├── optimizer.py
│   ├── pdf_parser.py
│   ├── preferences.py
│   └── utils.py
├── .gitignore
├── README.md
└── requirements.txt

After this, run one final test:

python src/main.py

If it still works, your Python prototype is in a good state.