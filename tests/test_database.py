"""Tests for database schema and CRUD operations."""

import os
import tempfile
import pytest
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


@pytest.fixture
def db_path():
    """Create a temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


# ---------------------------------------------------------------------------
# Rubric tests
# ---------------------------------------------------------------------------

class TestRubricCRUD:
    def test_create_and_get_rubric(self, db_path):
        rubric_id = create_rubric("Test Rubric", 100, db_path=db_path)
        assert rubric_id is not None

        rubric = get_rubric(rubric_id, db_path=db_path)
        assert rubric["title"] == "Test Rubric"
        assert rubric["total_marks"] == 100
        assert rubric["criteria"] == []

    def test_list_rubrics(self, db_path):
        create_rubric("Rubric A", 50, db_path=db_path)
        create_rubric("Rubric B", 70, db_path=db_path)

        rubrics = list_rubrics(db_path=db_path)
        assert len(rubrics) == 2
        titles = {r["title"] for r in rubrics}
        assert titles == {"Rubric A", "Rubric B"}

    def test_delete_rubric(self, db_path):
        rubric_id = create_rubric("To Delete", 10, db_path=db_path)
        assert delete_rubric(rubric_id, db_path=db_path) is True
        assert get_rubric(rubric_id, db_path=db_path) is None

    def test_delete_nonexistent_rubric(self, db_path):
        assert delete_rubric(9999, db_path=db_path) is False

    def test_update_rubric(self, db_path):
        rubric_id = create_rubric("Original", 50, db_path=db_path)
        assert update_rubric(rubric_id, "Updated", 75, db_path=db_path) is True

        rubric = get_rubric(rubric_id, db_path=db_path)
        assert rubric["title"] == "Updated"
        assert rubric["total_marks"] == 75

    def test_get_nonexistent_rubric(self, db_path):
        assert get_rubric(9999, db_path=db_path) is None


# ---------------------------------------------------------------------------
# Criterion tests
# ---------------------------------------------------------------------------

class TestCriterionCRUD:
    def test_add_criterion_without_descriptors(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        crit_id = add_criterion(rubric_id, "Criterion 1", 5, 0, db_path=db_path)

        rubric = get_rubric(rubric_id, db_path=db_path)
        assert len(rubric["criteria"]) == 1
        assert rubric["criteria"][0]["name"] == "Criterion 1"
        assert rubric["criteria"][0]["max_marks"] == 5
        assert rubric["criteria"][0]["descriptors"] == []

    def test_add_criterion_with_descriptors(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        descriptors = [
            {"level": 1, "text": "Poor"},
            {"level": 2, "text": "Good"},
            {"level": 3, "text": "Excellent"},
        ]
        add_criterion(rubric_id, "Quality", 6, 0, descriptors=descriptors, db_path=db_path)

        rubric = get_rubric(rubric_id, db_path=db_path)
        crit = rubric["criteria"][0]
        assert len(crit["descriptors"]) == 3
        assert crit["descriptors"][0]["descriptor_text"] == "Poor"
        assert crit["descriptors"][2]["descriptor_text"] == "Excellent"

    def test_criterion_ordering(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        add_criterion(rubric_id, "Second", 3, 1, db_path=db_path)
        add_criterion(rubric_id, "First", 3, 0, db_path=db_path)

        rubric = get_rubric(rubric_id, db_path=db_path)
        assert rubric["criteria"][0]["name"] == "First"
        assert rubric["criteria"][1]["name"] == "Second"

    def test_delete_criterion(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        crit_id = add_criterion(rubric_id, "To Remove", 5, 0, db_path=db_path)
        assert delete_criterion(crit_id, db_path=db_path) is True

        rubric = get_rubric(rubric_id, db_path=db_path)
        assert len(rubric["criteria"]) == 0

    def test_cascade_delete_rubric_removes_criteria(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        add_criterion(rubric_id, "Crit 1", 5, 0, db_path=db_path)
        add_criterion(rubric_id, "Crit 2", 5, 1, db_path=db_path)

        delete_rubric(rubric_id, db_path=db_path)
        assert get_rubric(rubric_id, db_path=db_path) is None


# ---------------------------------------------------------------------------
# Submission tests
# ---------------------------------------------------------------------------

class TestSubmissionCRUD:
    def test_create_and_get_submission(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        sub_id = create_submission(rubric_id, "Draft text here", "My Draft", db_path=db_path)

        sub = get_submission(sub_id, db_path=db_path)
        assert sub["title"] == "My Draft"
        assert sub["raw_text"] == "Draft text here"
        assert sub["rubric_id"] == rubric_id

    def test_list_submissions(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        create_submission(rubric_id, "Draft 1", "First", db_path=db_path)
        create_submission(rubric_id, "Draft 2", "Second", db_path=db_path)

        subs = list_submissions(db_path=db_path)
        assert len(subs) == 2

    def test_delete_submission(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        sub_id = create_submission(rubric_id, "Draft", db_path=db_path)
        assert delete_submission(sub_id, db_path=db_path) is True
        assert get_submission(sub_id, db_path=db_path) is None

    def test_default_title(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        sub_id = create_submission(rubric_id, "Draft text", db_path=db_path)
        sub = get_submission(sub_id, db_path=db_path)
        assert sub["title"] == "Untitled Draft"


# ---------------------------------------------------------------------------
# Text Chunk tests
# ---------------------------------------------------------------------------

class TestChunkCRUD:
    def test_save_and_get_chunks(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        sub_id = create_submission(rubric_id, "Full text", db_path=db_path)

        chunks = [
            {"text": "First chunk.", "start": 0, "end": 12},
            {"text": "Second chunk.", "start": 10, "end": 23},
        ]
        save_chunks(sub_id, chunks, db_path=db_path)

        result = get_chunks(sub_id, db_path=db_path)
        assert len(result) == 2
        assert result[0]["chunk_text"] == "First chunk."
        assert result[1]["chunk_text"] == "Second chunk."

    def test_save_chunks_replaces_existing(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        sub_id = create_submission(rubric_id, "Text", db_path=db_path)

        save_chunks(sub_id, [{"text": "Old", "start": 0, "end": 3}], db_path=db_path)
        save_chunks(sub_id, [{"text": "New", "start": 0, "end": 3}], db_path=db_path)

        result = get_chunks(sub_id, db_path=db_path)
        assert len(result) == 1
        assert result[0]["chunk_text"] == "New"


# ---------------------------------------------------------------------------
# Evidence Match tests
# ---------------------------------------------------------------------------

class TestEvidenceMatchCRUD:
    def test_save_and_get_evidence(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        crit_id = add_criterion(rubric_id, "Crit", 5, 0, db_path=db_path)
        sub_id = create_submission(rubric_id, "Text", db_path=db_path)
        save_chunks(sub_id, [{"text": "Chunk", "start": 0, "end": 5}], db_path=db_path)

        chunks = get_chunks(sub_id, db_path=db_path)
        chunk_id = chunks[0]["chunk_id"]

        matches = [
            {"criterion_id": crit_id, "chunk_id": chunk_id, "score": 0.85, "snippet": "Chunk"}
        ]
        save_evidence_matches(sub_id, matches, db_path=db_path)

        result = get_evidence_matches(sub_id, db_path=db_path)
        assert len(result) == 1
        assert result[0]["score"] == 0.85

    def test_filter_evidence_by_criterion(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        crit_a = add_criterion(rubric_id, "A", 5, 0, db_path=db_path)
        crit_b = add_criterion(rubric_id, "B", 5, 1, db_path=db_path)
        sub_id = create_submission(rubric_id, "Text", db_path=db_path)
        save_chunks(sub_id, [{"text": "Chunk", "start": 0, "end": 5}], db_path=db_path)
        chunks = get_chunks(sub_id, db_path=db_path)
        chunk_id = chunks[0]["chunk_id"]

        matches = [
            {"criterion_id": crit_a, "chunk_id": chunk_id, "score": 0.5, "snippet": "A match"},
            {"criterion_id": crit_b, "chunk_id": chunk_id, "score": 0.3, "snippet": "B match"},
        ]
        save_evidence_matches(sub_id, matches, db_path=db_path)

        result_a = get_evidence_matches(sub_id, criterion_id=crit_a, db_path=db_path)
        assert len(result_a) == 1
        assert result_a[0]["snippet"] == "A match"


# ---------------------------------------------------------------------------
# Report Item tests
# ---------------------------------------------------------------------------

class TestReportItemCRUD:
    def test_save_and_get_report_items(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        crit_id = add_criterion(rubric_id, "Crit", 5, 0, db_path=db_path)
        sub_id = create_submission(rubric_id, "Text", db_path=db_path)

        items = [
            {
                "criterion_id": crit_id,
                "status": "Strong",
                "rationale": "Good coverage.",
                "next_action": "None needed.",
                "evidence_strength": 0.9,
            }
        ]
        save_report_items(sub_id, items, db_path=db_path)

        result = get_report_items(sub_id, db_path=db_path)
        assert len(result) == 1
        assert result[0]["status"] == "Strong"
        assert result[0]["evidence_strength"] == 0.9


# ---------------------------------------------------------------------------
# Evaluation Run tests
# ---------------------------------------------------------------------------

class TestEvaluationRun:
    def test_create_evaluation_run(self, db_path):
        rubric_id = create_rubric("Test", 10, db_path=db_path)
        sub_id = create_submission(rubric_id, "Text", db_path=db_path)
        run_id = create_evaluation_run(sub_id, "tfidf", "Test run", db_path=db_path)
        assert run_id is not None
