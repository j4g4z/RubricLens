"""Tests for report generation, status classification, and rationale generation."""

import pytest
from backend.report_generator import (
    classify_status,
    compute_evidence_strength,
    generate_rationale,
    generate_next_action,
    generate_report,
)


# ---------------------------------------------------------------------------
# Status classification tests
# ---------------------------------------------------------------------------

class TestClassifyStatus:
    def test_missing_no_matches(self):
        assert classify_status([]) == "Missing"

    def test_missing_all_below_threshold(self):
        matches = [{"score": 0.01}, {"score": 0.02}]
        assert classify_status(matches) == "Missing"

    def test_partial_one_match(self):
        matches = [{"score": 0.10}]
        assert classify_status(matches) == "Partial"

    def test_partial_two_matches(self):
        matches = [{"score": 0.12}, {"score": 0.08}]
        assert classify_status(matches) == "Partial"

    def test_partial_low_top_score(self):
        matches = [{"score": 0.10}, {"score": 0.08}, {"score": 0.06}]
        assert classify_status(matches) == "Partial"

    def test_strong_three_matches_high_score(self):
        matches = [{"score": 0.30}, {"score": 0.20}, {"score": 0.15}]
        assert classify_status(matches) == "Strong"

    def test_strong_many_matches(self):
        matches = [{"score": 0.35}, {"score": 0.28}, {"score": 0.22}, {"score": 0.10}]
        assert classify_status(matches) == "Strong"

    def test_deterministic(self):
        """Same input must produce same output."""
        matches = [{"score": 0.30}, {"score": 0.20}, {"score": 0.15}]
        results = [classify_status(matches) for _ in range(10)]
        assert all(r == results[0] for r in results)


# ---------------------------------------------------------------------------
# Evidence strength tests
# ---------------------------------------------------------------------------

class TestComputeEvidenceStrength:
    def test_no_matches(self):
        assert compute_evidence_strength([]) == 0.0

    def test_single_match(self):
        assert compute_evidence_strength([{"score": 0.5}]) == 0.5

    def test_capped_at_one(self):
        assert compute_evidence_strength([{"score": 1.5}]) == 1.0

    def test_uses_max_score(self):
        matches = [{"score": 0.3}, {"score": 0.8}, {"score": 0.1}]
        assert compute_evidence_strength(matches) == 0.8


# ---------------------------------------------------------------------------
# Rationale generation tests
# ---------------------------------------------------------------------------

class TestGenerateRationale:
    def test_missing_rationale(self):
        rationale = generate_rationale(
            "Missing", "Iterative design", ["Evidence of iteration"], []
        )
        assert "No evidence found" in rationale
        assert "Iterative design" in rationale
        assert "Evidence of iteration" in rationale

    def test_partial_rationale(self):
        matches = [{"score": 0.10, "text": "Some relevant content here about design"}]
        rationale = generate_rationale(
            "Partial", "Code quality", ["Clean code"], matches
        )
        assert "Some relevant content" in rationale
        assert "Code quality" in rationale

    def test_strong_rationale(self):
        matches = [
            {"score": 0.30, "text": "Evidence 1"},
            {"score": 0.25, "text": "Evidence 2"},
            {"score": 0.20, "text": "Evidence 3"},
        ]
        rationale = generate_rationale(
            "Strong", "Testing", ["Well documented tests"], matches
        )
        assert "Multiple sections" in rationale
        assert "Testing" in rationale

    def test_rationale_without_descriptors(self):
        rationale = generate_rationale("Missing", "Something", [], [])
        assert "expected content" in rationale


# ---------------------------------------------------------------------------
# Next action generation tests
# ---------------------------------------------------------------------------

class TestGenerateNextAction:
    def test_missing_action(self):
        action = generate_next_action(
            "Missing", "Error handling", ["Effective error handling"], 2
        )
        assert "Add a section" in action
        assert "error handling" in action.lower()
        assert "2" in action

    def test_partial_action(self):
        action = generate_next_action(
            "Partial", "Testing", ["Systematic testing regime"], 4
        )
        assert "Expand" in action
        assert "testing" in action.lower()

    def test_strong_action(self):
        action = generate_next_action(
            "Strong", "Collaboration", ["Excellent collaboration"], 4
        )
        assert "Good coverage" in action


# ---------------------------------------------------------------------------
# Full report generation tests
# ---------------------------------------------------------------------------

class TestGenerateReport:
    @pytest.fixture
    def sample_criteria(self):
        return [
            {
                "criterion_id": 1,
                "name": "Iterative design",
                "max_marks": 4,
                "descriptors": ["No iteration", "Some iteration", "Good iteration", "Excellent iteration"],
            },
            {
                "criterion_id": 2,
                "name": "Error handling",
                "max_marks": 1,
                "descriptors": ["No error handling", "Effective error handling"],
            },
            {
                "criterion_id": 3,
                "name": "Testing",
                "max_marks": 2,
                "descriptors": ["No tests", "Well documented tests"],
            },
        ]

    def test_report_structure(self, sample_criteria):
        evidence = {1: [], 2: [], 3: []}
        report = generate_report(sample_criteria, evidence)
        assert "items" in report
        assert "summary" in report
        assert len(report["items"]) == 3

    def test_report_item_fields(self, sample_criteria):
        evidence = {1: [], 2: [], 3: []}
        report = generate_report(sample_criteria, evidence)
        item = report["items"][0]
        assert "criterion_id" in item
        assert "status" in item
        assert "evidence_strength" in item
        assert "rationale" in item
        assert "next_action" in item

    def test_summary_counts(self, sample_criteria):
        evidence = {
            1: [],  # Missing
            2: [{"score": 0.10, "text": "Error handling text"}],  # Partial
            3: [
                {"score": 0.30, "text": "Test 1"},
                {"score": 0.28, "text": "Test 2"},
                {"score": 0.22, "text": "Test 3"},
            ],  # Strong
        }
        report = generate_report(sample_criteria, evidence)
        summary = report["summary"]
        assert summary["missing"] == 1
        assert summary["partial"] == 1
        assert summary["strong"] == 1
        assert summary["total_criteria"] == 3

    def test_top_priorities(self, sample_criteria):
        evidence = {1: [], 2: [], 3: []}  # All missing
        report = generate_report(sample_criteria, evidence)
        priorities = report["summary"]["top_priorities"]
        assert len(priorities) <= 3
        # Should be sorted by max_marks descending
        if len(priorities) >= 2:
            assert priorities[0]["max_marks"] >= priorities[1]["max_marks"]

    def test_coverage_percentage(self, sample_criteria):
        evidence = {
            1: [
                {"score": 0.30, "text": "A"},
                {"score": 0.28, "text": "B"},
                {"score": 0.22, "text": "C"},
            ],
            2: [
                {"score": 0.30, "text": "D"},
                {"score": 0.28, "text": "E"},
                {"score": 0.22, "text": "F"},
            ],
            3: [
                {"score": 0.30, "text": "G"},
                {"score": 0.28, "text": "H"},
                {"score": 0.22, "text": "I"},
            ],
        }
        report = generate_report(sample_criteria, evidence)
        assert report["summary"]["coverage_pct"] == 100.0

    def test_empty_criteria(self):
        report = generate_report([], {})
        assert report["items"] == []
        assert report["summary"]["total_criteria"] == 0
        assert report["summary"]["coverage_pct"] == 0
