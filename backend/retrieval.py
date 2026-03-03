"""TF-IDF evidence retrieval engine with heuristic filters."""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class TFIDFRetriever:
    """Evidence retrieval using TF-IDF cosine similarity.

    For each rubric criterion, build a query from the criterion name
    and its descriptors, then compute cosine similarity against all
    text chunks. Returns top-k chunks above a relevance threshold.
    """

    def __init__(self, relevance_threshold: float = 0.05, top_k: int = 5):
        self.relevance_threshold = relevance_threshold
        self.top_k = top_k
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=10000,
            sublinear_tf=True,
        )
        self.chunk_vectors = None
        self.chunks = []

    def build_index(self, chunks: list[str]):
        """Fit TF-IDF on chunk texts and store vectors."""
        self.chunks = chunks
        if not chunks:
            self.chunk_vectors = None
            return
        self.chunk_vectors = self.vectorizer.fit_transform(chunks)

    def build_criterion_query(self, criterion_name: str, descriptors: list[str]) -> str:
        """Combine criterion name and all descriptor texts into a search query."""
        parts = [criterion_name] + descriptors
        return " ".join(parts)

    def retrieve(self, query: str) -> list[dict]:
        """Return top-k chunks by cosine similarity to query.

        Filters out chunks below relevance_threshold and chunks
        shorter than 15 words (too little context).

        Returns:
            List of {"chunk_index": int, "score": float, "text": str}
        """
        if self.chunk_vectors is None or not self.chunks:
            return []

        query_vector = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, self.chunk_vectors).flatten()

        # Build scored results
        scored = []
        for i, score in enumerate(similarities):
            if score < self.relevance_threshold:
                continue
            # Reject chunks shorter than 15 words
            if len(self.chunks[i].split()) < 15:
                continue
            scored.append({
                "chunk_index": i,
                "score": float(score),
                "text": self.chunks[i],
            })

        # Sort by score descending and take top-k
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[: self.top_k]

    def retrieve_all_criteria(
        self, criteria: list[dict], chunks: list[str]
    ) -> dict:
        """For each criterion, retrieve evidence chunks.

        Args:
            criteria: List of dicts with keys "criterion_id", "name",
                      and "descriptors" (list of descriptor text strings).
            chunks: List of chunk text strings.

        Returns:
            Dict mapping criterion_id to list of
            {"chunk_index": int, "score": float, "text": str}.
        """
        self.build_index(chunks)

        if not chunks:
            return {c["criterion_id"]: [] for c in criteria}

        results = {}
        total_criteria = len(criteria)

        # First pass: retrieve for each criterion
        raw_results = {}
        for criterion in criteria:
            query = self.build_criterion_query(
                criterion["name"],
                criterion.get("descriptors", []),
            )
            matches = self.retrieve(query)
            raw_results[criterion["criterion_id"]] = matches

        # Heuristic: detect generic chunks (matched by >60% of criteria)
        if total_criteria > 1:
            chunk_match_counts = {}
            for crit_id, matches in raw_results.items():
                for match in matches:
                    idx = match["chunk_index"]
                    chunk_match_counts[idx] = chunk_match_counts.get(idx, 0) + 1

            generic_chunks = {
                idx
                for idx, count in chunk_match_counts.items()
                if count > total_criteria * 0.6
            }

            # Downweight generic chunks by halving their score
            for crit_id, matches in raw_results.items():
                for match in matches:
                    if match["chunk_index"] in generic_chunks:
                        match["score"] *= 0.5
                # Re-filter after downweighting
                raw_results[crit_id] = [
                    m for m in matches if m["score"] >= self.relevance_threshold
                ]

        results = raw_results
        return results
