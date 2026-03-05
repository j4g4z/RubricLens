"""Tests for FastAPI routes."""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

# Set up test database before importing app
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_test_db_fd)

import backend.database as db_module
db_module.DB_PATH = _test_db_path
db_module.init_db(_test_db_path)

from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Reset database before each test."""
    db_module.init_db(_test_db_path)
    conn = db_module.get_connection(_test_db_path)
    for table in ["evidence_match", "report_item", "evaluation_run", "text_chunk",
                   "submission", "level_descriptor", "criterion", "rubric"]:
        conn.execute(f"DELETE FROM {table}")
    conn.commit()
    conn.close()
    yield


class TestHealthCheck:
    def test_health(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestRubricAPI:
    def test_create_rubric(self):
        response = client.post("/api/rubrics", json={"title": "Test Rubric", "total_marks": 50})
        assert response.status_code == 200
        assert "rubric_id" in response.json()

    def test_create_rubric_empty_title(self):
        response = client.post("/api/rubrics", json={"title": "", "total_marks": 0})
        assert response.status_code == 400

    def test_list_rubrics(self):
        client.post("/api/rubrics", json={"title": "A", "total_marks": 10})
        client.post("/api/rubrics", json={"title": "B", "total_marks": 20})
        response = client.get("/api/rubrics")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_rubric(self):
        r = client.post("/api/rubrics", json={"title": "Test", "total_marks": 30})
        rubric_id = r.json()["rubric_id"]
        response = client.get(f"/api/rubrics/{rubric_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Test"

    def test_get_nonexistent_rubric(self):
        response = client.get("/api/rubrics/9999")
        assert response.status_code == 404

    def test_delete_rubric(self):
        r = client.post("/api/rubrics", json={"title": "Delete Me", "total_marks": 0})
        rubric_id = r.json()["rubric_id"]
        response = client.delete(f"/api/rubrics/{rubric_id}")
        assert response.status_code == 200

    def test_add_criterion(self):
        r = client.post("/api/rubrics", json={"title": "Test", "total_marks": 10})
        rubric_id = r.json()["rubric_id"]
        response = client.post(
            f"/api/rubrics/{rubric_id}/criteria",
            json={
                "name": "Quality",
                "max_marks": 5,
                "order_index": 0,
                "descriptors": [{"level": 1, "text": "Poor"}, {"level": 2, "text": "Good"}],
            },
        )
        assert response.status_code == 200
        assert "criterion_id" in response.json()

    def test_seed_demo(self):
        response = client.post("/api/rubrics/seed-demo")
        assert response.status_code == 200
        rubric_id = response.json()["rubric_id"]

        rubric = client.get(f"/api/rubrics/{rubric_id}").json()
        assert rubric["title"] == "CM2020 Software Project \u2014 Final Assessment"
        assert len(rubric["criteria"]) == 17


class TestSubmissionAPI:
    def _create_rubric(self):
        r = client.post("/api/rubrics", json={"title": "Test", "total_marks": 10})
        rubric_id = r.json()["rubric_id"]
        client.post(
            f"/api/rubrics/{rubric_id}/criteria",
            json={"name": "Testing", "max_marks": 5, "descriptors": [{"level": 1, "text": "No tests"}, {"level": 2, "text": "Good tests"}]},
        )
        return rubric_id

    def test_create_submission(self):
        rubric_id = self._create_rubric()
        response = client.post("/api/submissions", json={
            "rubric_id": rubric_id,
            "title": "My Draft",
            "raw_text": "This is my test draft with enough words to form a proper submission for testing purposes here.",
        })
        assert response.status_code == 200
        data = response.json()
        assert "submission_id" in data
        assert data["word_count"] > 0

    def test_create_submission_empty_text(self):
        rubric_id = self._create_rubric()
        response = client.post("/api/submissions", json={
            "rubric_id": rubric_id,
            "raw_text": "   ",
        })
        assert response.status_code == 400

    def test_list_submissions(self):
        rubric_id = self._create_rubric()
        client.post("/api/submissions", json={"rubric_id": rubric_id, "raw_text": "Draft text here."})
        response = client.get("/api/submissions")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_delete_submission(self):
        rubric_id = self._create_rubric()
        r = client.post("/api/submissions", json={"rubric_id": rubric_id, "raw_text": "Draft text."})
        sub_id = r.json()["submission_id"]
        response = client.delete(f"/api/submissions/{sub_id}")
        assert response.status_code == 200


class TestAnalysisAPI:
    def _setup_submission(self):
        """Create rubric with criteria and a submission."""
        r = client.post("/api/rubrics/seed-demo")
        rubric_id = r.json()["rubric_id"]

        draft = (
            "This software project demonstrates iterative design through multiple "
            "development sprints and regular feedback loops. The testing approach uses "
            "pytest with comprehensive unit tests and integration tests covering all "
            "major components. Error handling is implemented with try-except blocks "
            "throughout the codebase. The user interface was evaluated through "
            "formative evaluation with representative stakeholders who provided "
            "actionable feedback on usability and design improvements."
        )
        r = client.post("/api/submissions", json={
            "rubric_id": rubric_id,
            "title": "Test Draft",
            "raw_text": draft,
        })
        return r.json()["submission_id"]

    def test_analyse(self):
        sub_id = self._setup_submission()
        response = client.post(f"/api/analyse/{sub_id}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "summary" in data
        assert data["summary"]["total_criteria"] == 17

    def test_get_report(self):
        sub_id = self._setup_submission()
        client.post(f"/api/analyse/{sub_id}")
        response = client.get(f"/api/report/{sub_id}")
        assert response.status_code == 200
        assert "items" in response.json()

    def test_get_report_before_analysis(self):
        r = client.post("/api/rubrics", json={"title": "Test", "total_marks": 10})
        rubric_id = r.json()["rubric_id"]
        r = client.post("/api/submissions", json={"rubric_id": rubric_id, "raw_text": "Some text."})
        sub_id = r.json()["submission_id"]
        response = client.get(f"/api/report/{sub_id}")
        assert response.status_code == 404

    def test_get_evidence(self):
        sub_id = self._setup_submission()
        client.post(f"/api/analyse/{sub_id}")

        # Get the rubric to find a criterion_id
        sub = client.get(f"/api/submissions/{sub_id}").json()
        rubric = client.get(f"/api/rubrics/{sub['rubric_id']}").json()
        crit_id = rubric["criteria"][0]["criterion_id"]

        response = client.get(f"/api/evidence/{sub_id}/{crit_id}")
        assert response.status_code == 200
        assert "evidence" in response.json()
        assert "criterion" in response.json()


class TestExportAPI:
    def _setup_analysed_submission(self):
        r = client.post("/api/rubrics/seed-demo")
        rubric_id = r.json()["rubric_id"]
        r = client.post("/api/submissions", json={
            "rubric_id": rubric_id,
            "title": "Export Test",
            "raw_text": "This is a test draft for export functionality testing purposes with enough content.",
        })
        sub_id = r.json()["submission_id"]
        client.post(f"/api/analyse/{sub_id}")
        return sub_id

    def test_export_markdown(self):
        sub_id = self._setup_analysed_submission()
        response = client.get(f"/api/export/{sub_id}/markdown")
        assert response.status_code == 200
        assert "RubricLens" in response.text

    def test_export_pdf(self):
        sub_id = self._setup_analysed_submission()
        response = client.get(f"/api/export/{sub_id}/pdf")
        assert response.status_code == 200
        assert response.content[:5] == b"%PDF-"
