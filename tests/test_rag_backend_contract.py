import pytest
from app.rag.fts import fts_search, rebuild_fts_index
from app.rag.hybrid import compare_fusion_rankings
from app.core import init_db

from app.rag.backend import RagBackendSettings, compare_ranked_ids


def test_sqlite_is_the_safe_default_backend():
    assert RagBackendSettings.from_env({}) == RagBackendSettings("sqlite", True)


def test_pgvector_requires_explicit_capability_verification():
    with pytest.raises(RuntimeError, match="capability"):
        RagBackendSettings.from_env({"RAG_BACKEND": "postgres_pgvector"})


def test_backend_rejects_unknown_values():
    with pytest.raises(ValueError, match="지원하지 않는"):
        RagBackendSettings.from_env({"RAG_BACKEND": "redis"})


def test_ranked_result_comparison_is_deterministic():
    result = compare_ranked_ids([{"id": 1}, {"id": 2}], [{"id": 2}, {"id": 3}])
    assert result["overlap_count"] == 1
    assert result["overlap_rate"] == 0.5
    assert result["order_changed"] is True


def test_fts5_index_is_derived_and_tracks_passage_changes(tmp_path):
    db = tmp_path / "fts.db"
    init_db(db)
    from app.repositories.bible import add_passage, delete_bible_translation

    add_passage("TEST", "ko", "JHN 1:1", "말씀이 계셨습니다", db_path=db)
    assert rebuild_fts_index(db) == 1
    assert fts_search("말씀", db_path=db)[0]["reference"] == "JHN 1:1"
    delete_bible_translation("TEST", db)
    assert fts_search("말씀", db_path=db) == []


def test_rrf_candidate_requires_overlap_before_canary_approval():
    baseline = [{"id": 1}, {"id": 2}, {"id": 3}]
    candidate = [{"id": 3}, {"id": 2}, {"id": 4}]
    result = compare_fusion_rankings(baseline, candidate, limit=3, minimum_overlap=0.70)
    assert result["overlap_count"] == 2
    assert result["overlap_rate"] == 0.6667
    assert result["order_changed"] is True
    assert result["approved_for_canary"] is False
