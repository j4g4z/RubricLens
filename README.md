# RubricLens

A rubric-aligned draft self-evaluation tool for university coursework.

## Overview

RubricLens helps students evaluate a coursework draft against a marking rubric by:

1. **Structuring rubric criteria** -- manual entry, JSON import, or demo rubric loading
2. **Locating evidence** in the draft for each criterion using TF-IDF retrieval
3. **Producing an explainable coverage report** with gap analysis and actionable improvements

This is **formative decision support**, not automated grading. It runs entirely locally with no external API calls required.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite (via sqlite3 stdlib) |
| Retrieval | scikit-learn (TF-IDF), numpy |
| Document parsing | python-docx for .docx files |
| Export | Markdown (built-in), PDF via fpdf2 |
| Frontend | Single-page HTML/CSS/JS (vanilla) |
| Testing | pytest, pytest-cov |

## Quick Start

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
# Opens at http://localhost:8000
```

## Running Tests

```bash
pytest tests/ -v --cov=backend
```

The test suite includes 113 tests across 6 test files covering all backend modules and API endpoints.

## User Guide

### 1. Loading a Rubric

When you first open RubricLens, you'll see the **Rubrics** view. You have three options:

- **Load Demo Rubric (CM2020)**: One-click loading of the CM2020 final assessment rubric with 17 criteria and performance descriptors. This is the fastest way to get started.
- **Create New Rubric**: Manually enter rubric title, total marks, criteria names, marks per criterion, and performance level descriptors.
- **Import Rubric (JSON)**: Upload a JSON file matching the format in `sample_data/cm2020_rubric.json`.

Click on any rubric in the list to select it and navigate to the Draft Input view.

### 2. Submitting a Draft

In the **Draft Input** view:

1. Select a rubric from the dropdown (auto-selected if you clicked from the rubrics list).
2. Give your draft a title.
3. Either **paste your draft text** into the text area (a live word count is displayed) or **upload a .docx file**.
4. Click **Analyse Draft**.

The system will normalise your text, split it into overlapping chunks, and run TF-IDF retrieval against each rubric criterion.

### 3. Reading the Coverage Report

The **Report** view shows:

- **Summary bar**: Counts of Strong, Partial, and Missing criteria, plus an overall coverage percentage.
- **Top 3 Priorities**: The most important gaps to address, sorted by marks weight.
- **Per-criterion cards**: Each criterion shows a colour-coded status badge (green = Strong, amber = Partial, red = Missing), an evidence strength bar, and a next-action suggestion.

### 4. Evidence Drill-down

Click any criterion card to expand it and see:

- **Why this status?**: An explanation referencing the rubric descriptors.
- **Next Action**: A concrete revision suggestion based on rubric language.
- **Rubric Descriptors**: The full descriptor text for this criterion.
- **Evidence Excerpts**: Matched text chunks from your draft with TF-IDF relevance scores.
- **No evidence found**: If applicable, guidance on what content the rubric expects.

### 5. Exporting Reports

Click **Export Markdown** or **Export PDF** to download the coverage report for offline review. The PDF includes colour-coded status badges and a formatted table layout.

### 6. Managing Data

- **Delete rubrics** from the rubrics list view.
- **Delete submissions** from the previous submissions list in the Draft Input view.
- All data is stored locally in SQLite -- no data leaves your machine.

## Project Structure

```
rubriclens/
├── backend/
│   ├── main.py              # FastAPI app and routes
│   ├── database.py          # SQLite init and CRUD
│   ├── text_processing.py   # Text normalisation, chunking, .docx extraction
│   ├── retrieval.py         # TF-IDF evidence retrieval
│   ├── report_generator.py  # Status rules and report generation
│   ├── export.py            # Markdown and PDF export
│   └── seed_data.py         # Demo rubric loader
├── frontend/
│   ├── index.html           # Single-page application
│   ├── style.css            # Styles
│   └── app.js               # Frontend logic
├── tests/                   # Test suite (113 tests)
├── sample_data/
│   ├── cm2020_rubric.json   # CM2020 rubric in JSON format
│   └── sample_draft.txt     # Sample coursework draft for testing
├── exports/                 # Generated reports
├── requirements.txt
├── run.py                   # Entry point
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/rubrics` | List all rubrics |
| POST | `/api/rubrics` | Create rubric |
| GET | `/api/rubrics/{id}` | Get rubric with criteria |
| PUT | `/api/rubrics/{id}` | Update rubric |
| DELETE | `/api/rubrics/{id}` | Delete rubric |
| POST | `/api/rubrics/{id}/criteria` | Add criterion |
| POST | `/api/rubrics/import` | Import rubric from JSON |
| POST | `/api/rubrics/seed-demo` | Load CM2020 demo rubric |
| POST | `/api/submissions` | Create submission (paste) |
| POST | `/api/submissions/upload` | Upload .docx file |
| GET | `/api/submissions` | List submissions |
| GET | `/api/submissions/{id}` | Get submission details |
| DELETE | `/api/submissions/{id}` | Delete submission |
| POST | `/api/analyse/{id}` | Run TF-IDF analysis |
| GET | `/api/report/{id}` | Get generated report |
| GET | `/api/evidence/{sub_id}/{crit_id}` | Get evidence for criterion |
| GET | `/api/export/{id}/markdown` | Download Markdown report |
| GET | `/api/export/{id}/pdf` | Download PDF report |
