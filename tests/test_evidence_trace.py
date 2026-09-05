from app.grounding.trace import build_evidence_trace, validate_citation_links


def test_evidence_snapshot_has_stable_checksum_and_source_ids():
    packet = [{"source_type": "scripture", "reference": "마태복음 1:1", "text": "본문"}]
    first = build_evidence_trace("마태복음 1:1의 말씀입니다.", packet)
    second = build_evidence_trace("마태복음 1:1의 말씀입니다.", packet)
    assert first["snapshot"]["snapshot_id"] == second["snapshot"]["snapshot_id"]
    assert first["snapshot"]["checksum"] == second["snapshot"]["checksum"]
    assert first["snapshot"]["evidence"][0]["evidence_id"]
    assert first["validation"]["ok"]


def test_citation_trace_rejects_nonexistent_evidence_id():
    result = validate_citation_links(
        [{"claim_id": "claim-1", "evidence_id": "missing-doc"}],
        [{"evidence_id": "real-doc", "text": "본문"}],
    )
    assert not result["ok"]
    assert result["invalid_links"][0]["evidence_id"] == "missing-doc"


def test_snapshot_preserves_multiple_chunks_with_same_source_id():
    result = build_evidence_trace(
        "마태복음 1:1과 마태복음 1:2를 읽으십시오.",
        [
            {"source_id": "document-1", "chunk_id": "chunk-1", "reference": "마태복음 1:1", "text": "첫 본문"},
            {"source_id": "document-1", "chunk_id": "chunk-2", "reference": "마태복음 1:2", "text": "둘째 본문"},
        ],
    )
    assert len(result["snapshot"]["evidence"]) == 2
    assert len(result["citation_links"]) == 2


def test_trace_keeps_claim_types_separate_from_application_sentences():
    result = build_evidence_trace("마태복음 1:1을 읽으십시오.", [{"reference": "마태복음 1:1", "text": "본문"}])
    assert result["claims"][0]["claim_type"] == "scripture_claim"
    assert result["citation_links"][0]["relation"] == "supports"
