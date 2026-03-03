# RubricLens

A rubric-aligned draft self-evaluation tool for university coursework.

## Overview

RubricLens helps students evaluate a coursework draft against a marking rubric by:

1. **Structuring rubric criteria** — manual entry, JSON import, or demo rubric loading
2. **Locating evidence** in the draft for each criterion using TF-IDF retrieval
3. **Producing an explainable coverage report** with gap analysis and actionable improvements

This is **formative decision support**, not automated grading. It runs entirely locally with no external API calls required.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Database**: SQLite
- **Retrieval**: scikit-learn (TF-IDF)
- **Document parsing**: python-docx
- **Export**: Markdown, PDF (fpdf2)
- **Frontend**: Vanilla HTML/CSS/JS

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
├── tests/                   # Test suite
├── sample_data/             # Demo rubric and sample drafts
├── exports/                 # Generated reports
├── requirements.txt
├── run.py                   # Entry point
└── README.md
```
