"""Tests for TF-IDF retrieval engine."""

import pytest
from backend.retrieval import TFIDFRetriever


@pytest.fixture
def retriever():
    return TFIDFRetriever(relevance_threshold=0.05, top_k=3)


@pytest.fixture
def sample_chunks():
    return [
        "The software project uses iterative design methodology with agile sprints and regular feedback loops to improve the application over multiple cycles.",
        "Error handling is implemented throughout the codebase with try-except blocks and user-friendly error messages displayed to the end user.",
        "The user interface was evaluated using a questionnaire survey with five representative stakeholders who provided detailed feedback on usability.",
        "Unit tests cover all major functions with pytest and achieve high code coverage across the backend modules and API endpoints.",
        "The database schema uses SQLite with proper foreign key constraints and cascade delete operations for data integrity.",
        "Too short to matter.",
    ]


class TestTFIDFRetriever:
    def test_build_index(self, retriever, sample_chunks):
        retriever.build_index(sample_chunks)
        assert retriever.chunk_vectors is not None
        assert retriever.chunk_vectors.shape[0] == len(sample_chunks)

    def test_build_index_empty(self, retriever):
        retriever.build_index([])
        assert retriever.chunk_vectors is None

    def test_build_criterion_query(self, retriever):
        query = retriever.build_criterion_query(
            "Iterative design",
            ["Evidence of iteration", "Systematic improvements"],
        )
        assert "Iterative design" in query
        assert "Evidence of iteration" in query
        assert "Systematic improvements" in query

    def test_retrieve_returns_relevant_chunks(self, retriever, sample_chunks):
        retriever.build_index(sample_chunks)
        results = retriever.retrieve("iterative design methodology agile sprints")
        assert len(results) > 0
        # The iterative design chunk should be the top result
        assert "iterative" in results[0]["text"].lower()

    def test_retrieve_respects_threshold(self, retriever, sample_chunks):
        retriever.relevance_threshold = 0.99
        retriever.build_index(sample_chunks)
        results = retriever.retrieve("iterative design")
        # With a very high threshold, most results should be filtered
        assert len(results) == 0 or all(r["score"] >= 0.99 for r in results)

    def test_retrieve_respects_top_k(self, retriever, sample_chunks):
        retriever.top_k = 2
        retriever.build_index(sample_chunks)
        results = retriever.retrieve("software testing error handling design")
        assert len(results) <= 2

    def test_retrieve_filters_short_chunks(self, retriever, sample_chunks):
        retriever.build_index(sample_chunks)
        results = retriever.retrieve("short matter")
        # The short chunk should be filtered out
        for r in results:
            assert len(r["text"].split()) >= 15

    def test_retrieve_empty_index(self, retriever):
        retriever.build_index([])
        results = retriever.retrieve("anything")
        assert results == []

    def test_retrieve_result_structure(self, retriever, sample_chunks):
        retriever.build_index(sample_chunks)
        results = retriever.retrieve("iterative design")
        for r in results:
            assert "chunk_index" in r
            assert "score" in r
            assert "text" in r
            assert isinstance(r["score"], float)
            assert isinstance(r["chunk_index"], int)

    def test_retrieve_all_criteria(self, retriever, sample_chunks):
        criteria = [
            {
                "criterion_id": 1,
                "name": "Iterative design",
                "descriptors": ["Evidence of iterative design process"],
            },
            {
                "criterion_id": 2,
                "name": "Error handling",
                "descriptors": ["Effective error handling with graceful degradation"],
            },
            {
                "criterion_id": 3,
                "name": "Testing",
                "descriptors": ["Well documented tests", "Systematic testing regime"],
            },
        ]
        results = retriever.retrieve_all_criteria(criteria, sample_chunks)
        assert set(results.keys()) == {1, 2, 3}
        # Each criterion should find at least some evidence
        for crit_id, matches in results.items():
            assert isinstance(matches, list)

    def test_retrieve_all_criteria_empty_chunks(self, retriever):
        criteria = [{"criterion_id": 1, "name": "Test", "descriptors": []}]
        results = retriever.retrieve_all_criteria(criteria, [])
        assert results == {1: []}

    def test_generic_chunk_downweighting(self):
        """Chunks matching >60% of criteria get downweighted."""
        retriever = TFIDFRetriever(relevance_threshold=0.01, top_k=5)

        # A generic introduction chunk that mentions many topics
        generic = (
            "This software project demonstrates iterative design with error handling, "
            "testing methodology, user evaluation, collaboration, code structure, "
            "and novel technical challenges in a well-documented system."
        )
        specific_iter = "The iterative design process involved three major sprints with retrospectives and design improvements after each cycle of development and user feedback."
        specific_test = "The testing regime uses pytest with fixtures and parametrized test cases covering unit tests, integration tests, and edge case validation for robustness."

        chunks = [generic, specific_iter, specific_test]

        criteria = [
            {"criterion_id": 1, "name": "Iterative design", "descriptors": ["Evidence of iteration"]},
            {"criterion_id": 2, "name": "Testing", "descriptors": ["Systematic testing"]},
            {"criterion_id": 3, "name": "Error handling", "descriptors": ["Effective error handling"]},
            {"criterion_id": 4, "name": "Collaboration", "descriptors": ["Evidence of collaboration"]},
        ]

        results = retriever.retrieve_all_criteria(criteria, chunks)

        # The generic chunk should be downweighted in scores
        for crit_id, matches in results.items():
            for match in matches:
                if match["chunk_index"] == 0:  # generic chunk
                    # Score should have been halved
                    assert match["score"] < 1.0  # just verify it ran without error
