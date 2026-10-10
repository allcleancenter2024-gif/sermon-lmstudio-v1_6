import pytest

from app.rag.quality import evaluate_query_set, validate_query_cases


def _row(identifier, reference):
    return {"id": identifier, "reference": reference}


def test_query_set_evaluation_aggregates_recall_mrr_and_lexical_top1():
    result = evaluate_query_set([
        {
            "query_id": "q-1",
            "baseline": [_row(1, "REF 1"), _row(2, "REF 2")],
            "candidate": [_row(1, "REF 1"), _row(2, "REF 2")],
            "lexical": [_row(1, "REF 1")],
            "relevant_references": ["REF 1"],
        },
        {
            "query_id": "q-2",
            "baseline": [_row(4, "REF 4"), _row(3, "REF 3")],
            "candidate": [_row(4, "REF 4"), _row(3, "REF 3")],
            "lexical": [_row(4, "REF 4")],
            "relevant_references": ["REF 3"],
        },
    ], k=2, minimum_overlap=0.5)

    assert result["query_count"] == 2
    assert result["average"]["candidate_recall_at_k"] == 1.0
    assert result["average"]["candidate_mrr_at_k"] == 0.75
    assert result["average"]["lexical_top1_relevant_rate"] == 0.5
    assert result["approved_for_canary"] is True


def test_empty_query_fixture_is_rejected_and_recall_drop_blocks_approval():
    with pytest.raises(ValueError):
        evaluate_query_set([])

    result = evaluate_query_set([
        {
            "query_id": "q-drop",
            "baseline": [_row(1, "REF 1")],
            "candidate": [_row(2, "REF 2")],
            "relevant_references": ["REF 1"],
        }
    ])
    assert result["queries"][0]["recall_drop"] == 1.0
    assert result["approved_for_rollout"] is False


def test_query_fixture_validator_rejects_duplicates_and_incomplete_rows():
    cases = [
        {"query_id": "q-1", "baseline": [{"id": 1}], "candidate": [], "relevant_references": []},
        {"query_id": "q-1", "baseline": [], "candidate": [], "relevant_references": ["REF 1"]},
    ]

    errors = validate_query_cases(cases)
    assert any("duplicate query_id" in error for error in errors)
    assert any("requires id and reference" in error for error in errors)
    assert any("relevant_references" in error for error in errors)
