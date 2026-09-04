import os

import pytest

from app.config import DB_PATH
from app.db_adapter import create_database_adapter
from app.rag.pgvector import PgVectorRagRepository
from app.rag.pgvector_migration import apply_pgvector_migration, reindex_sqlite_batch, rollback_pgvector_migration


pytestmark = pytest.mark.integration


MODEL = "text-embedding-nomic-embed-text-v1.5"


def test_pgvector_migration_incremental_reindex_and_safe_rollback():
    if os.environ.get("RUN_PGVECTOR_MIGRATION_INTEGRATION") != "1":
        pytest.skip("명시적 pgvector migration 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("PGVECTOR_DATABASE_URL", "")
    if "sermon_pgvector_test" not in url or "sermon_db" in url.replace("sermon_pgvector_test", ""):
        pytest.fail("통합시험 대상은 sermon_pgvector_test로 제한됩니다.")

    repository = PgVectorRagRepository(create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url}))
    repository.ensure_schema()
    with repository.adapter.transaction() as connection:
        connection.execute("DELETE FROM rag_pgvector_embeddings")
        connection.execute("DELETE FROM rag_pgvector_passages")
        connection.execute("DROP TABLE IF EXISTS rag_pgvector_schema_migrations")

    assert apply_pgvector_migration(repository)["applied"] is True
    assert apply_pgvector_migration(repository)["applied"] is False
    first = reindex_sqlite_batch(repository, DB_PATH, MODEL, batch_size=8)
    second = reindex_sqlite_batch(repository, DB_PATH, MODEL, offset=first["next_offset"], batch_size=8)
    assert first["written_embeddings"] == second["written_embeddings"] == 8
    with pytest.raises(RuntimeError, match="자동 삭제"):
        rollback_pgvector_migration(repository)

    with repository.adapter.transaction() as connection:
        connection.execute("DELETE FROM rag_pgvector_embeddings")
        connection.execute("DELETE FROM rag_pgvector_passages")
    assert rollback_pgvector_migration(repository)["rolled_back"] is True
    repository.ensure_schema()
