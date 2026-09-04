import pytest

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
