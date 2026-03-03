"""FastAPI application with all route definitions for RubricLens."""

import json
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel
from typing import Optional

from backend.database import (
    init_db,
    create_rubric,
    get_rubric,
    list_rubrics,
    delete_rubric,
    update_rubric,
    add_criterion,
    delete_criterion,
    create_submission,
    get_submission,
    list_submissions,
    delete_submission,
    save_chunks,
    get_chunks,
    save_evidence_matches,
    get_evidence_matches,
    save_report_items,
    get_report_items,
    create_evaluation_run,
)
from backend.text_processing import normalise_text, extract_docx_text, chunk_text, word_count
from backend.retrieval import TFIDFRetriever
from backend.report_generator import generate_report
from backend.export import export_markdown, export_pdf
from backend.seed_data import load_demo_rubric, load_rubric_from_json

import os

app = FastAPI(title="RubricLens", version="1.0.0")

# Serve frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class RubricCreate(BaseModel):
    title: str
    total_marks: float = 0


class RubricUpdate(BaseModel):
    title: str
    total_marks: float


class CriterionCreate(BaseModel):
    name: str
    max_marks: float = 0
    order_index: int = 0
    descriptors: Optional[list[dict]] = None


class SubmissionCreate(BaseModel):
    rubric_id: int
    title: str = "Untitled Draft"
    raw_text: str


# ---------------------------------------------------------------------------
# Root — serve index.html
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "RubricLens API is running. Frontend not found."}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Rubric endpoints
# ---------------------------------------------------------------------------

@app.get("/api/rubrics")
async def api_list_rubrics():
    return list_rubrics()


@app.post("/api/rubrics")
async def api_create_rubric(rubric: RubricCreate):
    if not rubric.title.strip():
        raise HTTPException(status_code=400, detail="Rubric title cannot be empty")
    rubric_id = create_rubric(rubric.title, rubric.total_marks)
    return {"rubric_id": rubric_id}


@app.get("/api/rubrics/{rubric_id}")
async def api_get_rubric(rubric_id: int):
    rubric = get_rubric(rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    return rubric


@app.put("/api/rubrics/{rubric_id}")
async def api_update_rubric(rubric_id: int, rubric: RubricUpdate):
    if not rubric.title.strip():
        raise HTTPException(status_code=400, detail="Rubric title cannot be empty")
    if not update_rubric(rubric_id, rubric.title, rubric.total_marks):
        raise HTTPException(status_code=404, detail="Rubric not found")
    return {"success": True}


@app.delete("/api/rubrics/{rubric_id}")
async def api_delete_rubric(rubric_id: int):
    if not delete_rubric(rubric_id):
        raise HTTPException(status_code=404, detail="Rubric not found")
    return {"success": True}


@app.post("/api/rubrics/{rubric_id}/criteria")
async def api_add_criterion(rubric_id: int, criterion: CriterionCreate):
    rubric = get_rubric(rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    if not criterion.name.strip():
        raise HTTPException(status_code=400, detail="Criterion name cannot be empty")
    crit_id = add_criterion(
        rubric_id,
        criterion.name,
        criterion.max_marks,
        criterion.order_index,
        criterion.descriptors,
    )
    return {"criterion_id": crit_id}


@app.delete("/api/criteria/{criterion_id}")
async def api_delete_criterion(criterion_id: int):
    if not delete_criterion(criterion_id):
        raise HTTPException(status_code=404, detail="Criterion not found")
    return {"success": True}


@app.post("/api/rubrics/import")
async def api_import_rubric(file: UploadFile = File(...)):
    try:
        content = await file.read()
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if "title" not in data:
        raise HTTPException(status_code=400, detail="JSON must contain a 'title' field")

    rubric_id = load_rubric_from_json(data)
    return {"rubric_id": rubric_id}


@app.post("/api/rubrics/seed-demo")
async def api_seed_demo():
    rubric_id = load_demo_rubric()
    return {"rubric_id": rubric_id}


# ---------------------------------------------------------------------------
# Submission endpoints
# ---------------------------------------------------------------------------

@app.post("/api/submissions")
async def api_create_submission(submission: SubmissionCreate):
    rubric = get_rubric(submission.rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")
    if not submission.raw_text.strip():
        raise HTTPException(status_code=400, detail="Draft text cannot be empty")

    normalised = normalise_text(submission.raw_text)
    sub_id = create_submission(submission.rubric_id, normalised, submission.title)

    # Chunk the text and save
    chunks = chunk_text(normalised)
    save_chunks(sub_id, chunks)

    return {
        "submission_id": sub_id,
        "word_count": word_count(normalised),
        "chunk_count": len(chunks),
    }


@app.post("/api/submissions/upload")
async def api_upload_submission(
    rubric_id: int = Form(...),
    title: str = Form("Untitled Draft"),
    file: UploadFile = File(...),
):
    rubric = get_rubric(rubric_id)
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    content = await file.read()
    try:
        raw_text = extract_docx_text(content)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse .docx file")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Document contains no text")

    normalised = normalise_text(raw_text)
    sub_id = create_submission(rubric_id, normalised, title)

    chunks = chunk_text(normalised)
    save_chunks(sub_id, chunks)

    return {
        "submission_id": sub_id,
        "word_count": word_count(normalised),
        "chunk_count": len(chunks),
    }


@app.get("/api/submissions")
async def api_list_submissions():
    return list_submissions()


@app.get("/api/submissions/{submission_id}")
async def api_get_submission(submission_id: int):
    sub = get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


@app.delete("/api/submissions/{submission_id}")
async def api_delete_submission(submission_id: int):
    if not delete_submission(submission_id):
        raise HTTPException(status_code=404, detail="Submission not found")
    return {"success": True}


# ---------------------------------------------------------------------------
# Analysis endpoints
# ---------------------------------------------------------------------------

@app.post("/api/analyse/{submission_id}")
async def api_analyse(submission_id: int):
    sub = get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    rubric = get_rubric(sub["rubric_id"])
    if not rubric:
        raise HTTPException(status_code=404, detail="Associated rubric not found")

    # Get chunks
    chunks_db = get_chunks(submission_id)
    if not chunks_db:
        raise HTTPException(status_code=400, detail="No text chunks found. Re-submit the draft.")

    chunk_texts = [c["chunk_text"] for c in chunks_db]

    # Build criteria list for retrieval
    criteria = []
    for c in rubric["criteria"]:
        criteria.append({
            "criterion_id": c["criterion_id"],
            "name": c["name"],
            "max_marks": c["max_marks"],
            "descriptors": [d["descriptor_text"] for d in c.get("descriptors", [])],
        })

    # Run TF-IDF retrieval
    retriever = TFIDFRetriever(relevance_threshold=0.05, top_k=5)
    evidence = retriever.retrieve_all_criteria(criteria, chunk_texts)

    # Save evidence matches
    all_matches = []
    for crit_id, matches in evidence.items():
        for match in matches:
            chunk_idx = match["chunk_index"]
            all_matches.append({
                "criterion_id": crit_id,
                "chunk_id": chunks_db[chunk_idx]["chunk_id"],
                "score": match["score"],
                "snippet": match["text"][:500],
            })
    save_evidence_matches(submission_id, all_matches)

    # Generate report
    report = generate_report(criteria, evidence)

    # Save report items
    save_report_items(submission_id, [
        {
            "criterion_id": item["criterion_id"],
            "status": item["status"],
            "rationale": item["rationale"],
            "next_action": item["next_action"],
            "evidence_strength": item["evidence_strength"],
        }
        for item in report["items"]
    ])

    # Create evaluation run
    create_evaluation_run(submission_id, "tfidf", f"Analysed {len(chunk_texts)} chunks against {len(criteria)} criteria")

    return report


@app.get("/api/report/{submission_id}")
async def api_get_report(submission_id: int):
    sub = get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    rubric = get_rubric(sub["rubric_id"])
    if not rubric:
        raise HTTPException(status_code=404, detail="Associated rubric not found")

    report_items = get_report_items(submission_id)
    if not report_items:
        raise HTTPException(status_code=404, detail="No report found. Run analysis first.")

    # Rebuild report structure from saved items
    criteria_map = {c["criterion_id"]: c for c in rubric["criteria"]}
    items = []
    status_counts = {"Missing": 0, "Partial": 0, "Strong": 0}

    for ri in report_items:
        crit = criteria_map.get(ri["criterion_id"], {})
        status_counts[ri["status"]] = status_counts.get(ri["status"], 0) + 1
        evidence_matches = get_evidence_matches(submission_id, ri["criterion_id"])
        items.append({
            "criterion_id": ri["criterion_id"],
            "criterion_name": crit.get("name", "Unknown"),
            "max_marks": crit.get("max_marks", 0),
            "status": ri["status"],
            "evidence_strength": ri["evidence_strength"],
            "rationale": ri["rationale"],
            "next_action": ri["next_action"],
            "evidence_count": len(evidence_matches),
        })

    total = len(items)
    coverage_pct = round(status_counts.get("Strong", 0) / total * 100, 1) if total > 0 else 0

    priorities = sorted(
        [i for i in items if i["status"] in ("Missing", "Partial")],
        key=lambda x: x["max_marks"],
        reverse=True,
    )[:3]

    return {
        "items": items,
        "summary": {
            "total_criteria": total,
            "missing": status_counts.get("Missing", 0),
            "partial": status_counts.get("Partial", 0),
            "strong": status_counts.get("Strong", 0),
            "coverage_pct": coverage_pct,
            "top_priorities": [
                {
                    "criterion_name": p["criterion_name"],
                    "status": p["status"],
                    "max_marks": p["max_marks"],
                    "next_action": p["next_action"],
                }
                for p in priorities
            ],
        },
    }


@app.get("/api/evidence/{submission_id}/{criterion_id}")
async def api_get_evidence(submission_id: int, criterion_id: int):
    sub = get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    matches = get_evidence_matches(submission_id, criterion_id)

    # Get report item for this criterion
    report_items = get_report_items(submission_id)
    report_item = next((ri for ri in report_items if ri["criterion_id"] == criterion_id), None)

    # Get criterion details
    rubric = get_rubric(sub["rubric_id"])
    criterion = None
    if rubric:
        criterion = next(
            (c for c in rubric["criteria"] if c["criterion_id"] == criterion_id),
            None,
        )

    return {
        "criterion": {
            "name": criterion["name"] if criterion else "Unknown",
            "max_marks": criterion["max_marks"] if criterion else 0,
            "descriptors": [d["descriptor_text"] for d in criterion.get("descriptors", [])] if criterion else [],
        } if criterion else None,
        "report": {
            "status": report_item["status"],
            "rationale": report_item["rationale"],
            "next_action": report_item["next_action"],
            "evidence_strength": report_item["evidence_strength"],
        } if report_item else None,
        "evidence": [dict(m) for m in matches],
    }


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------

@app.get("/api/export/{submission_id}/markdown")
async def api_export_markdown(submission_id: int):
    sub = get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    rubric = get_rubric(sub["rubric_id"])
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    # Get stored report
    report_items = get_report_items(submission_id)
    if not report_items:
        raise HTTPException(status_code=404, detail="No report found. Run analysis first.")

    # Rebuild report for export
    criteria_map = {c["criterion_id"]: c for c in rubric["criteria"]}
    items = []
    status_counts = {"Missing": 0, "Partial": 0, "Strong": 0}

    for ri in report_items:
        crit = criteria_map.get(ri["criterion_id"], {})
        status_counts[ri["status"]] = status_counts.get(ri["status"], 0) + 1
        items.append({
            "criterion_id": ri["criterion_id"],
            "criterion_name": crit.get("name", "Unknown"),
            "max_marks": crit.get("max_marks", 0),
            "status": ri["status"],
            "evidence_strength": ri["evidence_strength"],
            "rationale": ri["rationale"],
            "next_action": ri["next_action"],
            "evidence_count": 0,
        })

    total = len(items)
    coverage_pct = round(status_counts.get("Strong", 0) / total * 100, 1) if total > 0 else 0

    priorities = sorted(
        [i for i in items if i["status"] in ("Missing", "Partial")],
        key=lambda x: x["max_marks"],
        reverse=True,
    )[:3]

    report = {
        "items": items,
        "summary": {
            "total_criteria": total,
            "missing": status_counts.get("Missing", 0),
            "partial": status_counts.get("Partial", 0),
            "strong": status_counts.get("Strong", 0),
            "coverage_pct": coverage_pct,
            "top_priorities": [
                {"criterion_name": p["criterion_name"], "status": p["status"],
                 "max_marks": p["max_marks"], "next_action": p["next_action"]}
                for p in priorities
            ],
        },
    }

    md_content = export_markdown(report, rubric["title"], sub["title"])
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="report_{submission_id}.md"'},
    )


@app.get("/api/export/{submission_id}/pdf")
async def api_export_pdf(submission_id: int):
    sub = get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    rubric = get_rubric(sub["rubric_id"])
    if not rubric:
        raise HTTPException(status_code=404, detail="Rubric not found")

    report_items = get_report_items(submission_id)
    if not report_items:
        raise HTTPException(status_code=404, detail="No report found. Run analysis first.")

    # Rebuild report for export
    criteria_map = {c["criterion_id"]: c for c in rubric["criteria"]}
    items = []
    status_counts = {"Missing": 0, "Partial": 0, "Strong": 0}

    for ri in report_items:
        crit = criteria_map.get(ri["criterion_id"], {})
        status_counts[ri["status"]] = status_counts.get(ri["status"], 0) + 1
        items.append({
            "criterion_id": ri["criterion_id"],
            "criterion_name": crit.get("name", "Unknown"),
            "max_marks": crit.get("max_marks", 0),
            "status": ri["status"],
            "evidence_strength": ri["evidence_strength"],
            "rationale": ri["rationale"],
            "next_action": ri["next_action"],
            "evidence_count": 0,
        })

    total = len(items)
    coverage_pct = round(status_counts.get("Strong", 0) / total * 100, 1) if total > 0 else 0

    priorities = sorted(
        [i for i in items if i["status"] in ("Missing", "Partial")],
        key=lambda x: x["max_marks"],
        reverse=True,
    )[:3]

    report = {
        "items": items,
        "summary": {
            "total_criteria": total,
            "missing": status_counts.get("Missing", 0),
            "partial": status_counts.get("Partial", 0),
            "strong": status_counts.get("Strong", 0),
            "coverage_pct": coverage_pct,
            "top_priorities": [
                {"criterion_name": p["criterion_name"], "status": p["status"],
                 "max_marks": p["max_marks"], "next_action": p["next_action"]}
                for p in priorities
            ],
        },
    }

    pdf_content = export_pdf(report, rubric["title"], sub["title"])
    return Response(
        content=bytes(pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{submission_id}.pdf"'},
    )
