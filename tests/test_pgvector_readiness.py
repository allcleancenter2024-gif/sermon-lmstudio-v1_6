import pytest

from app.rag.pgvector_readiness import MAX_CANARY_ROWS, load_sqlite_canary_rows


def test_canary_loader_rejects_unsafe_limits(tmp_path):
    with pytest.raises(ValueError, match="canary limit"):
        load_sqlite_canary_rows(tmp_path / "source.sqlite3", "model", limit=0)
    with pytest.raises(ValueError, match="canary limit"):
        load_sqlite_canary_rows(tmp_path / "source.sqlite3", "model", limit=MAX_CANARY_ROWS + 1)
