"""Pure semantic-scoring helpers independent of Provider and persistence."""
from __future__ import annotations

from array import array
import json
import math

from app.repositories.rag import fetch_rag_stats, fetch_rag_vector_rows
from app.rag.backend import RagBackendSettings
from app.rag.pgvector import create_pgvector_repository


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return cosine similarity, preserving Core's invalid-vector sentinel."""
    if len(a) != len(b) or not a:
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else -1.0


_cosine = cosine_similarity


def restore_rag_vector(vector_blob, vector_json):
    """Restore a stored binary vector, falling back to the legacy JSON form."""
    if vector_blob:
        vector_array = array("f")
        vector_array.frombytes(vector_blob)
        return vector_array
    return json.loads(vector_json)


def score_semantic_vector(query_vector, vector, stored_norm) -> float:
    """Score one restored vector using the stored norm when available."""
    if stored_norm:
        qnorm = math.sqrt(sum(x * x for x in query_vector))
        dot = sum(x * y for x, y in zip(query_vector, vector))
        return dot / (qnorm * stored_norm) if qnorm else -1.0
    return cosine_similarity(query_vector, vector)


def _sqlite_semantic_search(query_vector, model: str, limit: int, db_path=None) -> list[dict]:
    if db_path is None:
        rows = fetch_rag_vector_rows(model)
    else:
        rows = fetch_rag_vector_rows(model, db_path)
    scored = []
    for raw in rows:
        item = dict(raw)
        vector = restore_rag_vector(item.pop("vector_blob"), item.pop("vector_json"))
        stored_norm = item.pop("norm")
        item["semantic_score"] = score_semantic_vector(query_vector, vector, stored_norm)
        scored.append(item)
    return sorted(scored, key=lambda item: item["semantic_score"], reverse=True)[:limit]


def semantic_search(query: str, client, model: str, limit: int = 20, db_path=None) -> list[dict]:
    """Search the selected backend, preserving SQLite as the safe fallback."""
    query_vector = client.embeddings(model, [query])[0]
    settings = RagBackendSettings.from_env()
    if settings.name != "postgres_pgvector" or not settings.enabled:
        return _sqlite_semantic_search(query_vector, model, limit, db_path)
    try:
        repository = create_pgvector_repository()
        return repository.search(query_vector, model, limit)
    except Exception:
        if not settings.fallback_to_sqlite:
            raise
        return _sqlite_semantic_search(query_vector, model, limit, db_path)
