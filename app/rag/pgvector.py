"""Explicit PostgreSQL/pgvector Bible RAG repository.

This module is opt-in and is not connected to the production search path yet.
The separate table namespace prevents collisions with the existing SQLite RAG
and with the earlier object-storage rehearsal tables.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import math
import os
from urllib.parse import quote

from app.db_adapter import PostgresAdapter


MODEL_DIMENSION = 768
HNSW_EF_SEARCH = 200
PGVECTOR_CONNECT_TIMEOUT_SECONDS = 1


class PgVectorConfigurationError(ValueError):
    """Raised when pgvector input does not match the approved contract."""


def vector_literal(values: Sequence[float]) -> str:
    if len(values) != MODEL_DIMENSION:
        raise PgVectorConfigurationError(f"pgvector 임베딩 차원은 {MODEL_DIMENSION}이어야 합니다.")
    if not all(math.isfinite(float(value)) for value in values):
        raise PgVectorConfigurationError("pgvector 임베딩에는 유한한 숫자만 허용됩니다.")
    return "[" + ",".join(format(float(value), ".9g") for value in values) + "]"


class PgVectorRagRepository:
    """Repository for an explicitly provisioned PostgreSQL pgvector schema."""

    backend = "postgres_pgvector"

    def __init__(self, adapter):
        if getattr(adapter, "backend", None) != "postgres":
            raise PgVectorConfigurationError("pgvector Repository에는 PostgreSQL adapter가 필요합니다.")
        self.adapter = adapter

    def ensure_schema(self) -> None:
        with self.adapter.transaction() as connection:
            connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS rag_pgvector_passages (
                    id BIGINT PRIMARY KEY, translation TEXT NOT NULL, language TEXT NOT NULL,
                    reference TEXT NOT NULL, text TEXT NOT NULL, license_note TEXT NOT NULL DEFAULT ''
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS rag_pgvector_embeddings (
                    passage_id BIGINT NOT NULL REFERENCES rag_pgvector_passages(id) ON DELETE CASCADE,
                    model TEXT NOT NULL, dimension INTEGER NOT NULL CHECK (dimension = 768),
                    embedding vector(768) NOT NULL, PRIMARY KEY (passage_id, model)
                )"""
            )
            connection.execute(
                """CREATE INDEX IF NOT EXISTS ix_rag_pgvector_embeddings_model_cosine
                   ON rag_pgvector_embeddings USING hnsw (embedding vector_cosine_ops)"""
            )

    def upsert_passages(self, rows: Iterable[dict]) -> int:
        values = [(int(row["id"]), row["translation"], row["language"], row["reference"], row["text"], row.get("license_note", "")) for row in rows]
        with self.adapter.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """INSERT INTO rag_pgvector_passages (id, translation, language, reference, text, license_note)
                       VALUES (%s, %s, %s, %s, %s, %s)
                       ON CONFLICT (id) DO UPDATE SET translation=excluded.translation,
                       language=excluded.language, reference=excluded.reference, text=excluded.text,
                       license_note=excluded.license_note""", values
                )
        return len(values)

    def upsert_embeddings(self, rows: Iterable[tuple[int, Sequence[float]]], model: str) -> int:
        if not model or not model.strip():
            raise PgVectorConfigurationError("임베딩 모델명이 필요합니다.")
        values = [(int(passage_id), model.strip(), MODEL_DIMENSION, vector_literal(vector)) for passage_id, vector in rows]
        with self.adapter.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    """INSERT INTO rag_pgvector_embeddings (passage_id, model, dimension, embedding)
                       VALUES (%s, %s, %s, %s::vector)
                       ON CONFLICT (passage_id, model) DO UPDATE SET dimension=excluded.dimension,
                       embedding=excluded.embedding""", values
                )
        return len(values)

    def search(self, query_vector: Sequence[float], model: str, limit: int = 20) -> list[dict]:
        if limit < 1 or limit > 100:
            raise PgVectorConfigurationError("검색 limit은 1부터 100 사이여야 합니다.")
        literal = vector_literal(query_vector)
        with self.adapter.transaction() as connection:
            # HNSW is approximate by design.  A wider bounded search keeps the
            # live path stable for the small (<=100) result windows we expose.
            connection.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(HNSW_EF_SEARCH),))
            rows = connection.execute(
                """SELECT p.id, p.translation, p.language, p.reference, p.text, p.license_note,
                          1 - (e.embedding <=> %s::vector) AS semantic_score
                   FROM rag_pgvector_embeddings e JOIN rag_pgvector_passages p ON p.id=e.passage_id
                   WHERE e.model=%s ORDER BY e.embedding <=> %s::vector LIMIT %s""",
                (literal, model.strip(), literal, limit),
            ).fetchall()
        return [dict(row) for row in rows]


def create_pgvector_repository(environ: dict[str, str] | None = None) -> PgVectorRagRepository:
    """Create an explicit pgvector repository without reusing generic DB URLs.

    A dedicated URL prevents an object-storage or migration-rehearsal database
    from accidentally becoming the live RAG backend.
    """
    env = os.environ if environ is None else environ
    database_url = env.get("RAG_PGVECTOR_DATABASE_URL", "").strip()
    if not database_url:
        database_name = env.get("POSTGRES_RAG_PROD_DB", "").strip()
        username = env.get("POSTGRES_RAG_PROD_USER", "").strip()
        password = env.get("POSTGRES_RAG_PROD_PASSWORD", "")
        port = env.get("POSTGRES_RAG_PROD_PORT", "15434").strip()
        if all((database_name, username, password, port)):
            database_url = (
                f"postgresql://{quote(username, safe='')}:{quote(password, safe='')}"
                f"@127.0.0.1:{quote(port, safe='')}/{quote(database_name, safe='')}"
            )
    if not database_url:
        raise PgVectorConfigurationError(
            "pgvector RAG에는 RAG_PGVECTOR_DATABASE_URL 또는 전용 POSTGRES_RAG_PROD 연결 정보가 필요합니다."
        )
    return PgVectorRagRepository(
        PostgresAdapter(database_url, connect_timeout_seconds=PGVECTOR_CONNECT_TIMEOUT_SECONDS)
    )
