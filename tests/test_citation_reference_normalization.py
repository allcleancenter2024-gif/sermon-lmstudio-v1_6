from app.core import analyze_citations, validate_quotes


def test_korean_display_reference_matches_canonical_db_reference():
    passages = [{"reference": "JHN 8:32", "text": "And you will know the truth."}]
    sermon = "요한복음 8:32에서 예수님은 진리를 말씀하십니다."

    assert validate_quotes(sermon, passages) == []
    result = analyze_citations(sermon, passages)
    assert result["unsupported_count"] == 0
    assert result["mappings"][0]["references"] == ["JHN 8:32"]
