import pytest

from app.rag.pgvector_readiness import MAX_CANARY_ROWS, audit_pgvector_canary, load_sqlite_canary_rows


def test_canary_loader_rejects_unsafe_limits(tmp_path):
    with pytest.raises(ValueError, match="canary limit"):
        load_sqlite_canary_rows(tmp_path / "source.sqlite3", "model", limit=0)
    with pytest.raises(ValueError, match="canary limit"):
        load_sqlite_canary_rows(tmp_path / "source.sqlite3", "model", limit=MAX_CANARY_ROWS + 1)


def test_canary_rejects_expected_count_smaller_than_sample():
    with pytest.raises(ValueError, match="expected_embedding_count"):
        audit_pgvector_canary(object(), [{"id": 1}], "model", [[0.0]], expected_embedding_count=0)


def test_canary_rejects_empty_full_rank_baseline():
    with pytest.raises(ValueError, match="검색 순위 기준"):
        audit_pgvector_canary(object(), [{"id": 1}], "model", [[0.0]], baseline_rows=[])
