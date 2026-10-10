"""Read-only quality gates for comparing RAG ranking candidates."""

from __future__ import annotations


def recall_at_k(ranked: list[dict], relevant_references: set[str], k: int = 5) -> float:
    """Return binary relevance recall for the first ``k`` ranked rows."""
    if not relevant_references:
        return 1.0
    found = {str(row.get("reference", "")) for row in ranked[:k]}
    return round(len(found & relevant_references) / len(relevant_references), 4)


def mean_reciprocal_rank(ranked: list[dict], relevant_references: set[str], k: int = 5) -> float:
    """Return reciprocal rank of the first relevant result, or zero."""
    for index, row in enumerate(ranked[:k], start=1):
        if str(row.get("reference", "")) in relevant_references:
            return round(1.0 / index, 4)
    return 0.0


def validate_query_cases(cases: list[dict]) -> list[str]:
    """Validate query-set structure before calculating quality metrics."""
    errors: list[str] = []
    if not isinstance(cases, list) or not cases:
        return ["query fixture must contain at least one case"]
    seen_ids: set[str] = set()
    for index, case in enumerate(cases, start=1):
        prefix = f"case {index}"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        query_id = str(case.get("query_id") or "").strip()
        if not query_id:
            errors.append(f"{prefix} query_id is required")
        elif query_id in seen_ids:
            errors.append(f"duplicate query_id: {query_id}")
        seen_ids.add(query_id)
        for ranking_name in ("baseline", "candidate"):
            ranking = case.get(ranking_name)
            if not isinstance(ranking, list):
                errors.append(f"{prefix} {ranking_name} must be a list")
                continue
            for row_index, row in enumerate(ranking, start=1):
                if not isinstance(row, dict):
                    errors.append(f"{prefix} {ranking_name}[{row_index}] must be a mapping")
                elif not str(row.get("id") or "").strip() or not str(row.get("reference") or "").strip():
                    errors.append(f"{prefix} {ranking_name}[{row_index}] requires id and reference")
        relevant = case.get("relevant_references")
        if not isinstance(relevant, list) or not {str(item).strip() for item in relevant if str(item).strip()}:
            errors.append(f"{prefix} relevant_references must contain at least one reference")
        lexical = case.get("lexical")
        if lexical is not None and not isinstance(lexical, list):
            errors.append(f"{prefix} lexical must be a list when provided")
    return errors


def evaluate_fusion_quality(
    baseline: list[dict],
    candidate: list[dict],
    relevant_references: set[str],
    *,
    k: int = 5,
    minimum_overlap: float = 0.70,
    max_recall_drop: float = 0.0,
    max_mrr_drop: float = 0.0,
) -> dict:
    """Evaluate a candidate without changing the active RAG strategy."""
    baseline_recall = recall_at_k(baseline, relevant_references, k)
    candidate_recall = recall_at_k(candidate, relevant_references, k)
    baseline_mrr = mean_reciprocal_rank(baseline, relevant_references, k)
    candidate_mrr = mean_reciprocal_rank(candidate, relevant_references, k)
    baseline_ids = {row.get("id") for row in baseline[:k]}
    candidate_ids = {row.get("id") for row in candidate[:k]}
    overlap = len(baseline_ids & candidate_ids) / max(len(baseline_ids), 1)
    recall_drop = round(baseline_recall - candidate_recall, 4)
    mrr_drop = round(baseline_mrr - candidate_mrr, 4)
    return {
        "k": k,
        "baseline_recall_at_k": baseline_recall,
        "candidate_recall_at_k": candidate_recall,
        "baseline_mrr_at_k": baseline_mrr,
        "candidate_mrr_at_k": candidate_mrr,
        "recall_drop": recall_drop,
        "mrr_drop": mrr_drop,
        "overlap_rate": round(overlap, 4),
        "minimum_overlap": minimum_overlap,
        "max_recall_drop": max_recall_drop,
        "max_mrr_drop": max_mrr_drop,
        "approved_for_rollout": (
            bool(baseline_ids)
            and overlap >= minimum_overlap
            and recall_drop <= max_recall_drop
            and mrr_drop <= max_mrr_drop
        ),
    }


def evaluate_query_set(
    cases: list[dict],
    *,
    k: int = 5,
    minimum_overlap: float = 0.70,
    max_recall_drop: float = 0.0,
    max_mrr_drop: float = 0.0,
) -> dict:
    """Aggregate read-only ranking metrics for an approved query fixture.

    Each case contains ``query_id``, ``baseline``, ``candidate``, and
    ``relevant_references``.  An optional ``lexical`` list is used only for a
    top-1 diagnostic.  This function does not select a RAG strategy or write
    results anywhere.
    """
    validation_errors = validate_query_cases(cases)
    if validation_errors:
        raise ValueError("query fixture validation failed: " + "; ".join(validation_errors))
    rows: list[dict] = []
    for index, case in enumerate(cases, start=1):
        query_id = str(case.get("query_id") or f"case-{index}")
        baseline = list(case.get("baseline") or [])
        candidate = list(case.get("candidate") or [])
        relevant = {str(reference) for reference in (case.get("relevant_references") or []) if str(reference)}
        metrics = evaluate_fusion_quality(
            baseline,
            candidate,
            relevant,
            k=k,
            minimum_overlap=minimum_overlap,
            max_recall_drop=max_recall_drop,
            max_mrr_drop=max_mrr_drop,
        )
        lexical = list(case.get("lexical") or [])
        lexical_top1 = str(lexical[0].get("reference")) if lexical and lexical[0].get("reference") else None
        rows.append({
            "query_id": query_id,
            **metrics,
            "lexical_top1": lexical_top1,
            "lexical_top1_relevant": bool(lexical_top1 and lexical_top1 in relevant),
        })
    average = {
        "baseline_recall_at_k": round(sum(row["baseline_recall_at_k"] for row in rows) / len(rows), 4),
        "candidate_recall_at_k": round(sum(row["candidate_recall_at_k"] for row in rows) / len(rows), 4),
        "baseline_mrr_at_k": round(sum(row["baseline_mrr_at_k"] for row in rows) / len(rows), 4),
        "candidate_mrr_at_k": round(sum(row["candidate_mrr_at_k"] for row in rows) / len(rows), 4),
        "overlap_rate": round(sum(row["overlap_rate"] for row in rows) / len(rows), 4),
        "lexical_top1_relevant_rate": round(sum(row["lexical_top1_relevant"] for row in rows) / len(rows), 4),
    }
    return {
        "k": k,
        "query_count": len(rows),
        "average": average,
        "queries": rows,
        "approved_for_canary": all(row["approved_for_rollout"] for row in rows),
        "approved_for_rollout": all(row["approved_for_rollout"] for row in rows),
    }
