"""Report generation with deterministic status rules, rationales, and next actions."""


def classify_status(matches: list[dict], threshold: float = 0.05) -> str:
    """Classify evidence status for a criterion.

    Rules (deterministic):
        - Missing: No chunk above relevance threshold
        - Partial: 1-2 chunks above threshold, OR top score < 0.15
        - Strong:  3+ relevant chunks AND top score > 0.25

    Args:
        matches: List of evidence matches with "score" keys.
        threshold: Minimum score to count as relevant.

    Returns:
        "Missing", "Partial", or "Strong".
    """
    relevant = [m for m in matches if m["score"] >= threshold]

    if len(relevant) == 0:
        return "Missing"

    top_score = max(m["score"] for m in relevant)

    if len(relevant) >= 3 and top_score > 0.25:
        return "Strong"

    return "Partial"


def compute_evidence_strength(matches: list[dict]) -> float:
    """Compute normalised evidence strength from match scores.

    Returns the top TF-IDF score capped at 1.0.
    """
    if not matches:
        return 0.0
    top_score = max(m["score"] for m in matches)
    return min(top_score, 1.0)


def generate_rationale(
    status: str,
    criterion_name: str,
    descriptors: list[str],
    matches: list[dict],
) -> str:
    """Generate a 1-2 sentence rationale explaining the status.

    References rubric descriptor language for specificity.
    """
    descriptor_summary = "; ".join(descriptors[:3]) if descriptors else "the expected content"

    if status == "Missing":
        return (
            f"No evidence found in your draft addressing '{criterion_name}'. "
            f"The rubric expects: {descriptor_summary}."
        )

    if status == "Partial":
        matched_count = len([m for m in matches if m["score"] >= 0.05])
        if matched_count == 1:
            snippet_preview = matches[0]["text"][:80] + "..." if len(matches[0]["text"]) > 80 else matches[0]["text"]
            return (
                f"Some relevant content was found for '{criterion_name}', "
                f"but coverage appears limited. Found reference near: \"{snippet_preview}\". "
                f"The rubric also expects: {descriptor_summary}."
            )
        return (
            f"Some relevant content was found for '{criterion_name}', "
            f"but it may not fully address all aspects. "
            f"The rubric expects: {descriptor_summary}."
        )

    # Strong
    matched_count = len([m for m in matches if m["score"] >= 0.05])
    return (
        f"Multiple sections of your draft ({matched_count} relevant passages) "
        f"provide evidence for '{criterion_name}', "
        f"covering key aspects of: {descriptor_summary}."
    )


def generate_next_action(
    status: str,
    criterion_name: str,
    descriptors: list[str],
    max_marks: float,
) -> str:
    """Generate a concrete revision suggestion from rubric descriptor language."""
    # Use the highest-level descriptor for guidance
    top_descriptor = descriptors[-1] if descriptors else criterion_name

    if status == "Missing":
        return (
            f"Add a section discussing {criterion_name.lower()}. "
            f"The rubric's top level expects: \"{top_descriptor}\". "
            f"This criterion is worth {max_marks} marks."
        )

    if status == "Partial":
        return (
            f"Expand your existing discussion of {criterion_name.lower()} "
            f"to more fully address: \"{top_descriptor}\". "
            f"Consider adding specific examples or evidence to strengthen coverage."
        )

    # Strong
    return (
        f"Good coverage of {criterion_name.lower()}. "
        f"Review your draft to ensure it clearly demonstrates: \"{top_descriptor}\"."
    )


def generate_report(criteria: list[dict], evidence: dict) -> dict:
    """Generate a full coverage report from criteria and evidence matches.

    Args:
        criteria: List of criterion dicts with keys:
            criterion_id, name, max_marks, descriptors (list of str)
        evidence: Dict mapping criterion_id to list of evidence matches
            [{"chunk_index": int, "score": float, "text": str}]

    Returns:
        Dict with "items" (list of report items) and "summary".
    """
    items = []
    status_counts = {"Missing": 0, "Partial": 0, "Strong": 0}

    for criterion in criteria:
        crit_id = criterion["criterion_id"]
        matches = evidence.get(crit_id, [])
        descriptors = criterion.get("descriptors", [])

        status = classify_status(matches)
        strength = compute_evidence_strength(matches)
        rationale = generate_rationale(status, criterion["name"], descriptors, matches)
        next_action = generate_next_action(
            status, criterion["name"], descriptors, criterion.get("max_marks", 0)
        )

        status_counts[status] += 1

        items.append({
            "criterion_id": crit_id,
            "criterion_name": criterion["name"],
            "max_marks": criterion.get("max_marks", 0),
            "status": status,
            "evidence_strength": strength,
            "rationale": rationale,
            "next_action": next_action,
            "evidence_count": len([m for m in matches if m["score"] >= 0.05]),
        })

    # Summary
    total_criteria = len(criteria)
    coverage_pct = (
        round(status_counts["Strong"] / total_criteria * 100, 1)
        if total_criteria > 0
        else 0
    )

    # Top 3 priorities: Missing/Partial criteria sorted by max_marks descending
    priorities = sorted(
        [i for i in items if i["status"] in ("Missing", "Partial")],
        key=lambda x: x["max_marks"],
        reverse=True,
    )[:3]

    summary = {
        "total_criteria": total_criteria,
        "missing": status_counts["Missing"],
        "partial": status_counts["Partial"],
        "strong": status_counts["Strong"],
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
    }

    return {"items": items, "summary": summary}
