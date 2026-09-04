import os
import uuid

import pytest

from app.db_adapter import create_database_adapter


pytestmark = pytest.mark.integration


def test_pgvector_extension_and_vector_search_capability():
    if os.environ.get("RUN_PGVECTOR_INTEGRATION") != "1":
        pytest.skip("명시적 pgvector capability 통합시험 플래그가 없어 건너뜁니다.")

    url = os.environ.get("PGVECTOR_DATABASE_URL", "")
    if "sermon_pgvector_test" not in url or "sermon_db" in url.replace("sermon_pgvector_test", ""):
        pytest.fail("통합시험 대상은 sermon_pgvector_test로 제한됩니다.")

    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    row_id = str(uuid.uuid4())
    with adapter.transaction() as connection:
        extension = connection.execute(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        assert extension is not None
        connection.execute(
            "INSERT INTO rag_embedding_probe (id, embedding) VALUES (%s, %s::vector)",
            (row_id, "[1,0,0]"),
        )
        nearest = connection.execute(
            "SELECT id FROM rag_embedding_probe ORDER BY embedding <=> %s::vector LIMIT 1",
            ("[1,0,0]",),
        ).fetchone()
        assert nearest["id"] == row_id

    with pytest.raises(RuntimeError):
        with adapter.transaction() as connection:
            connection.execute("DELETE FROM rag_embedding_probe WHERE id=%s", (row_id,))
            raise RuntimeError("capability rollback")

    with adapter.transaction() as connection:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM rag_embedding_probe WHERE id=%s", (row_id,)
        ).fetchone()
        assert remaining["count"] == 1
        connection.execute("DELETE FROM rag_embedding_probe WHERE id=%s", (row_id,))
