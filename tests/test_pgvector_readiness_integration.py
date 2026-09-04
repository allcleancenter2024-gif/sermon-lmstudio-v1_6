import os

import pytest

from app.config import DB_PATH
from app.db_adapter import create_database_adapter
from app.rag.pgvector import PgVectorRagRepository
from app.rag.pgvector_migration import apply_pgvector_migration, reindex_sqlite_batch, rollback_pgvector_migration
from app.rag.pgvector_readiness import audit_pgvector_canary, load_sqlite_canary_rows
from app.rag.semantic import restore_rag_vector


pytestmark = pytest.mark.integration


MODEL = "text-embedding-nomic-embed-text-v1.5"


def test_canary_readiness_requires_counts_and_matching_ranks():
    if os.environ.get("RUN_PGVECTOR_READINESS_INTEGRATION") != "1":
        pytest.skip("명시적 pgvector readiness 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("PGVECTOR_DATABASE_URL", "")
    if "sermon_pgvector_test" not in url or "sermon_db" in url.replace("sermon_pgvector_test", ""):
        pytest.fail("통합시험 대상은 sermon_pgvector_test로 제한됩니다.")

    repository = PgVectorRagRepository(create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url}))
    repository.ensure_schema()
    with repository.adapter.transaction() as connection:
        connection.execute("DELETE FROM rag_pgvector_embeddings")
        connection.execute("DELETE FROM rag_pgvector_passages")
        connection.execute("DROP TABLE IF EXISTS rag_pgvector_schema_migrations")
    apply_pgvector_migration(repository)
    reindex_sqlite_batch(repository, DB_PATH, MODEL, batch_size=16)
    rows = load_sqlite_canary_rows(DB_PATH, MODEL, limit=16)
    queries = [restore_rag_vector(rows[index]["vector_blob"], rows[index]["vector_json"]) for index in (0, 8)]
    result = audit_pgvector_canary(repository, rows, MODEL, queries, top_k=5, max_latency_ms=1_000, expected_embedding_count=16)
    assert result["status"] == "PASS"

    with repository.adapter.transaction() as connection:
        connection.execute("DELETE FROM rag_pgvector_embeddings WHERE passage_id=%s", (rows[-1]["id"],))
    blocked = audit_pgvector_canary(repository, rows, MODEL, queries, top_k=5, max_latency_ms=1_000)
    assert blocked["status"] == "BLOCKED"
    assert blocked["checks"]["embedding_count_matches"] is False

    with repository.adapter.transaction() as connection:
        connection.execute("DELETE FROM rag_pgvector_embeddings")
        connection.execute("DELETE FROM rag_pgvector_passages")
    assert rollback_pgvector_migration(repository)["rolled_back"] is True
    repository.ensure_schema()
