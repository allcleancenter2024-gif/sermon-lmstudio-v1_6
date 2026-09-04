"""Explicit pgvector RAG migration and SQLite-to-pgvector rehearsal helpers.

Nothing in this module runs during application startup.  Operators must invoke
it after a backup and a separate approval, and rollback refuses populated data.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

from app.rag.pgvector import PgVectorConfigurationError, PgVectorRagRepository
from app.rag.semantic import restore_rag_vector


MIGRATION_ID = "rag_pgvector_v1"
MAX_BATCH_SIZE = 1_000


def _require_pgvector_repository(repository: PgVectorRagRepository) -> None:
    if not isinstance(repository, PgVectorRagRepository):
        raise PgVectorConfigurationError("pgvector migration에는 PgVectorRagRepository가 필요합니다.")


def apply_pgvector_migration(repository: PgVectorRagRepository) -> dict:
    """Provision the additive schema and record a single explicit migration ID."""
    _require_pgvector_repository(repository)
    repository.ensure_schema()
    with repository.adapter.transaction() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS rag_pgvector_schema_migrations (
                migration_id TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        existing = connection.execute(
            "SELECT migration_id FROM rag_pgvector_schema_migrations WHERE migration_id=%s",
            (MIGRATION_ID,),
        ).fetchone()
        if existing:
            return {"migration_id": MIGRATION_ID, "applied": False}
        connection.execute(
            "INSERT INTO rag_pgvector_schema_migrations (migration_id) VALUES (%s)",
            (MIGRATION_ID,),
        )
    return {"migration_id": MIGRATION_ID, "applied": True}


def rollback_pgvector_migration(repository: PgVectorRagRepository) -> dict:
    """Drop only an unused schema; populated RAG data must be restored from backup."""
    _require_pgvector_repository(repository)
    with repository.adapter.transaction() as connection:
        marker = connection.execute(
            "SELECT to_regclass('public.rag_pgvector_schema_migrations') AS name"
        ).fetchone()
        if not marker or not marker["name"]:
            return {"migration_id": MIGRATION_ID, "rolled_back": False, "reason": "migration_not_applied"}
        applied = connection.execute(
            "SELECT migration_id FROM rag_pgvector_schema_migrations WHERE migration_id=%s",
            (MIGRATION_ID,),
        ).fetchone()
        if not applied:
            return {"migration_id": MIGRATION_ID, "rolled_back": False, "reason": "migration_not_applied"}
        embedding_count = connection.execute("SELECT COUNT(*) AS count FROM rag_pgvector_embeddings").fetchone()["count"]
        passage_count = connection.execute("SELECT COUNT(*) AS count FROM rag_pgvector_passages").fetchone()["count"]
        if embedding_count or passage_count:
            raise RuntimeError("사용 중인 pgvector RAG 데이터는 자동 삭제 롤백하지 않습니다. 백업 복원을 사용하세요.")
        connection.execute("DROP TABLE IF EXISTS rag_pgvector_embeddings")
        connection.execute("DROP TABLE IF EXISTS rag_pgvector_passages")
        connection.execute("DROP TABLE IF EXISTS rag_pgvector_schema_migrations")
    return {"migration_id": MIGRATION_ID, "rolled_back": True}


def reindex_sqlite_batch(repository: PgVectorRagRepository, db_path: Path, model: str, *, offset: int = 0, batch_size: int = 250) -> dict:
    """Copy one bounded SQLite embedding batch without modifying the source DB."""
    if offset < 0:
        raise ValueError("offset은 0 이상이어야 합니다.")
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size는 1부터 {MAX_BATCH_SIZE} 사이여야 합니다.")
    _require_pgvector_repository(repository)
    with sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(row) for row in connection.execute(
            """SELECT p.id, p.translation, p.language, p.reference, p.text, p.license_note,
                      e.vector_json, e.vector_blob
               FROM rag_embeddings e JOIN passages p ON p.id=e.passage_id
               WHERE e.model=? ORDER BY p.id LIMIT ? OFFSET ?""",
            (model, batch_size, offset),
        )]
    passages = [{key: row[key] for key in ("id", "translation", "language", "reference", "text", "license_note")} for row in rows]
    embeddings = [(row["id"], restore_rag_vector(row["vector_blob"], row["vector_json"])) for row in rows]
    written_passages = repository.upsert_passages(passages) if passages else 0
    written_embeddings = repository.upsert_embeddings(embeddings, model) if embeddings else 0
    return {
        "offset": offset,
        "batch_size": batch_size,
        "written_passages": written_passages,
        "written_embeddings": written_embeddings,
        "next_offset": offset + len(rows),
        "complete": len(rows) < batch_size,
    }
