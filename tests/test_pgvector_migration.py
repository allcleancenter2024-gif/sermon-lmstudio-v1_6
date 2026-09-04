import sqlite3

import pytest

from app.rag.pgvector_migration import MAX_BATCH_SIZE, reindex_sqlite_batch


def test_reindex_batch_rejects_unsafe_bounds(tmp_path):
    db = tmp_path / "source.sqlite3"
    sqlite3.connect(db).close()
    with pytest.raises(ValueError, match="offset"):
        reindex_sqlite_batch(object(), db, "model", offset=-1)
    with pytest.raises(ValueError, match="batch_size"):
        reindex_sqlite_batch(object(), db, "model", batch_size=MAX_BATCH_SIZE + 1)
