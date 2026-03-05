"""Tests for Markdown and PDF export."""

import os
import tempfile
import pytest
from backend.export import export_markdown, export_pdf, save_markdown, save_pdf


@pytest.fixture
def sample_report():
    return {
        "items": [
            {
                "criterion_id": 1,
                "criterion_name": "Iterative design",
                "max_marks": 4,
                "status": "Strong",
                "evidence_strength": 0.85,
                "rationale": "Multiple sections provide evidence.",
                "next_action": "Review to ensure completeness.",
                "evidence_count": 3,
            },
            {
                "criterion_id": 2,
                "criterion_name": "Error handling",
                "max_marks": 1,
                "status": "Missing",
                "evidence_strength": 0.0,
                "rationale": "No evidence found.",
                "next_action": "Add error handling discussion.",
                "evidence_count": 0,
            },
            {
                "criterion_id": 3,
                "criterion_name": "Testing",
                "max_marks": 2,
                "status": "Partial",
                "evidence_strength": 0.12,
                "rationale": "Some coverage found.",
                "next_action": "Expand testing section.",
                "evidence_count": 1,
            },
        ],
        "summary": {
            "total_criteria": 3,
            "missing": 1,
            "partial": 1,
            "strong": 1,
            "coverage_pct": 33.3,
            "top_priorities": [
                {
                    "criterion_name": "Iterative design",
                    "status": "Partial",
                    "max_marks": 4,
                    "next_action": "Expand coverage.",
                },
            ],
        },
    }


class TestMarkdownExport:
    def test_contains_title(self, sample_report):
        md = export_markdown(sample_report, "Test Rubric", "My Draft")
        assert "# RubricLens Coverage Report" in md

    def test_contains_rubric_name(self, sample_report):
        md = export_markdown(sample_report, "Test Rubric", "My Draft")
        assert "Test Rubric" in md

    def test_contains_summary(self, sample_report):
        md = export_markdown(sample_report, "Test Rubric", "My Draft")
        assert "Strong" in md
        assert "Missing" in md
        assert "33.3%" in md

    def test_contains_criteria(self, sample_report):
        md = export_markdown(sample_report, "Test Rubric", "My Draft")
        assert "Iterative design" in md
        assert "Error handling" in md
        assert "Testing" in md

    def test_contains_table(self, sample_report):
        md = export_markdown(sample_report, "Test Rubric", "My Draft")
        assert "| Criterion |" in md

    def test_contains_priorities(self, sample_report):
        md = export_markdown(sample_report, "Test Rubric", "My Draft")
        assert "Top Priorities" in md

    def test_save_markdown(self, sample_report):
        with tempfile.TemporaryDirectory() as tmpdir:
            import backend.export as export_module
            original_dir = export_module.EXPORTS_DIR
            export_module.EXPORTS_DIR = tmpdir
            try:
                path = save_markdown(sample_report, "Test", "Draft", "test.md")
                assert os.path.exists(path)
                with open(path) as f:
                    content = f.read()
                assert "RubricLens" in content
            finally:
                export_module.EXPORTS_DIR = original_dir


class TestPDFExport:
    def test_returns_bytes(self, sample_report):
        pdf_bytes = export_pdf(sample_report, "Test Rubric", "My Draft")
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert len(pdf_bytes) > 0

    def test_valid_pdf_header(self, sample_report):
        pdf_bytes = export_pdf(sample_report, "Test Rubric", "My Draft")
        assert pdf_bytes[:5] == b"%PDF-"

    def test_save_pdf(self, sample_report):
        with tempfile.TemporaryDirectory() as tmpdir:
            import backend.export as export_module
            original_dir = export_module.EXPORTS_DIR
            export_module.EXPORTS_DIR = tmpdir
            try:
                path = save_pdf(sample_report, "Test", "Draft", "test.pdf")
                assert os.path.exists(path)
                with open(path, "rb") as f:
                    assert f.read(5) == b"%PDF-"
            finally:
                export_module.EXPORTS_DIR = original_dir

    def test_empty_report(self):
        report = {
            "items": [],
            "summary": {
                "total_criteria": 0,
                "missing": 0,
                "partial": 0,
                "strong": 0,
                "coverage_pct": 0,
                "top_priorities": [],
            },
        }
        pdf_bytes = export_pdf(report, "Empty", "Empty")
        assert pdf_bytes[:5] == b"%PDF-"
