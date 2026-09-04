"""Read-only canary readiness audit for the explicit pgvector RAG path."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from time import perf_counter
from typing import Sequence

from app.rag.backend import compare_ranked_ids
from app.rag.pgvector import PgVectorConfigurationError, PgVectorRagRepository
from app.rag.pgvector_migration import MIGRATION_ID
from app.rag.semantic import restore_rag_vector, score_semantic_vector


MAX_CANARY_ROWS = 1_000
MAX_LATENCY_MS = 60_000


def load_sqlite_canary_rows(db_path: Path, model: str, *, limit: int = 256) -> list[dict]:
    """Read bounded SQLite source rows without opening the source for writes."""
    if not 1 <= limit <= MAX_CANARY_ROWS:
        raise ValueError(f"canary limit은 1부터 {MAX_CANARY_ROWS} 사이여야 합니다.")
    with sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(
            """SELECT p.id, p.translation, p.language, p.reference, p.text, p.license_note,
                      e.vector_json, e.vector_blob, e.norm
               FROM rag_embeddings e JOIN passages p ON p.id=e.passage_id
               WHERE e.model=? ORDER BY p.id LIMIT ?""",
            (model, limit),
        )]


def audit_pgvector_canary(
    repository: PgVectorRagRepository,
    source_rows: list[dict],
    model: str,
    query_vectors: Sequence[Sequence[float]],
    *,
    top_k: int = 10,
    max_latency_ms: float = 5_000,
) -> dict:
    """Return PASS only when migration, count, rank, and latency gates all pass."""
    if not isinstance(repository, PgVectorRagRepository):
        raise PgVectorConfigurationError("canary audit에는 PgVectorRagRepository가 필요합니다.")
    if not source_rows:
        raise ValueError("canary 원본 행이 필요합니다.")
    if not query_vectors:
        raise ValueError("canary 질의 벡터가 필요합니다.")
    if not 1 <= top_k <= 100:
        raise ValueError("top_k는 1부터 100 사이여야 합니다.")
    if not 0 < max_latency_ms <= MAX_LATENCY_MS:
        raise ValueError(f"max_latency_ms는 0보다 크고 {MAX_LATENCY_MS} 이하여야 합니다.")

    with repository.adapter.transaction() as connection:
        migration_table = connection.execute(
            "SELECT to_regclass('public.rag_pgvector_schema_migrations') AS name"
        ).fetchone()
        migration_row = None
        if migration_table and migration_table["name"]:
            migration_row = connection.execute(
                "SELECT migration_id FROM rag_pgvector_schema_migrations WHERE migration_id=%s",
                (MIGRATION_ID,),
            ).fetchone()
        count_row = connection.execute(
            "SELECT COUNT(*) AS count FROM rag_pgvector_embeddings WHERE model=%s",
            (model,),
        ).fetchone()

    checks = {
        "migration_recorded": bool(migration_row),
        "embedding_count_matches": int(count_row["count"]) == len(source_rows),
    }
    comparisons = []
    for query_vector in query_vectors:
        baseline = []
        for row in source_rows:
            score = score_semantic_vector(
                query_vector,
                restore_rag_vector(row["vector_blob"], row["vector_json"]),
                row["norm"],
            )
            baseline.append({"id": row["id"], "semantic_score": score})
        baseline.sort(key=lambda row: row["semantic_score"], reverse=True)
        started = perf_counter()
        candidate = repository.search(query_vector, model, limit=top_k)
        latency_ms = (perf_counter() - started) * 1_000
        comparison = compare_ranked_ids(baseline, candidate, limit=top_k)
        comparison["latency_ms"] = round(latency_ms, 3)
        comparison["rank_matches"] = not comparison["order_changed"] and comparison["overlap_count"] == min(top_k, len(baseline))
        comparison["latency_passes"] = latency_ms <= max_latency_ms
        comparisons.append(comparison)

    checks["rank_matches"] = all(item["rank_matches"] for item in comparisons)
    checks["latency_within_budget"] = all(item["latency_passes"] for item in comparisons)
    return {
        "status": "PASS" if all(checks.values()) else "BLOCKED",
        "checks": checks,
        "model": model,
        "source_count": len(source_rows),
        "pgvector_count": int(count_row["count"]),
        "top_k": top_k,
        "max_latency_ms": max_latency_ms,
        "comparisons": comparisons,
    }
