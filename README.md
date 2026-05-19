# NTU STARS Timetable Optimizer

## Link

https://ntu-stars-optimizer.netlify.app/


## Why I Built This

NTU STARS registration moves fast. Your timetable planning should be faster.

Instead of manually comparing endless index combinations and only realising later that a lecture, tutorial, or lab clashes, this tool checks the combinations for you. Upload your module schedule PDFs, set your preferences, and get clash-free timetable options automatically.


## Features

- Upload multiple NTU class schedule PDFs
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
User uploads one class schedule PDF per module
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
````

## Project Structure

```text
ntu-stars-optimizer/
│
├── data/
│   └── preferences.json
│
├── frontend/
│   ├── app/
│   ├── public/
│   ├── package.json
│   └── ...
│
├── outputs/
│   └── generated JSON outputs locally
│
├── src/
│   ├── api.py
│   ├── main.py
│   ├── pdf_parser.py
│   ├── optimizer.py
│   ├── preferences.py
│   ├── utils.py
│   └── models.py
│
├── requirements.txt
├── README.md
└── .gitignore
```

## Tech Stack

```text
Frontend: Next.js, React, TypeScript, Tailwind CSS
Backend: Python, FastAPI
PDF Parsing: pdfplumber
Deployment: Netlify frontend + Render backend
```

## Setup

Clone the repository:

```bash
git clone https://github.com/Hemang131203/ntu-stars-optimizer.git
cd ntu-stars-optimizer
```

Create and activate a Python virtual environment:

```bash
python -m venv venv
```

On Windows PowerShell:

```bash
.\venv\Scripts\Activate.ps1
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Create the frontend environment file:

```bash
cd frontend
```

Create a file named `.env.local` and add:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Install frontend dependencies:

```bash
npm install
```

## Running Locally

Start the backend from the project root:

```bash
uvicorn src.api:app --reload
```

The backend runs at:

```text
http://localhost:8000
```

Start the frontend from the `frontend` folder:

```bash
npm run dev
```

The frontend runs at:

```text
http://localhost:3000
```

## Usage

1. Download or print one NTU class schedule PDF per module.
2. Open the web app.
3. Upload all module PDFs.
4. Select timetable preferences.
5. Click Generate Timetable.
6. View the top recommended clash-free timetables.

## Example Preferences

```json
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
```

## Clash Logic

Two classes clash only if their timings overlap on the same day.

Back-to-back classes are allowed.

Example:

```text
13:30-15:30
15:30-17:30
```

This is not a clash.

The overlap condition is:

```text
class_a_start < class_b_end
AND
class_b_start < class_a_end
```

## Preference Logic

The only mandatory rule is:

```text
No class timing clashes
```

All other preferences affect ranking only.

Lectures are included in clash checking but ignored by preference scoring by default.

This means if a user blocks Monday 12:30-14:00, a lecture in that window is acceptable, but a tutorial or lab in that window receives a penalty.

## Privacy Note

Uploaded PDFs are used only for timetable generation. The deployed backend processes the files temporarily and does not intentionally store uploaded PDFs.

## Current Status

This project is live and usable as a web application.

Live app:

```text
https://ntu-stars-optimizer.netlify.app/
```

````

After replacing, run:

```bash
git add README.md
git commit -m "Clean up README"
git push
````
