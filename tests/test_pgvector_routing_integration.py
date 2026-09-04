import os
import uuid

import pytest

from app.db_adapter import create_database_adapter
from app.rag.pgvector import MODEL_DIMENSION, PgVectorRagRepository
from app.rag.semantic import semantic_search


pytestmark = pytest.mark.integration


class _EmbeddingClient:
    def embeddings(self, _model, _texts):
        return [[1.0] + [0.0] * (MODEL_DIMENSION - 1)]


def test_feature_flag_routes_to_actual_pgvector_repository(monkeypatch):
    if os.environ.get("RUN_PGVECTOR_ROUTING_INTEGRATION") != "1":
        pytest.skip("명시적 pgvector routing 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("PGVECTOR_DATABASE_URL", "")
    if "sermon_pgvector_test" not in url or "sermon_db" in url.replace("sermon_pgvector_test", ""):
        pytest.fail("통합시험 대상은 sermon_pgvector_test로 제한됩니다.")

    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    repository = PgVectorRagRepository(adapter)
    repository.ensure_schema()
    passage_id = 910000 + int(uuid.uuid4().int % 9999)
    model = "text-embedding-nomic-embed-text-v1.5"
    repository.upsert_passages([{"id": passage_id, "translation": "TEST", "language": "ko", "reference": "경로 1:1", "text": "pgvector 경로 검증", "license_note": "test"}])
    repository.upsert_embeddings([(passage_id, [1.0] + [0.0] * (MODEL_DIMENSION - 1))], model)

    monkeypatch.setenv("RAG_BACKEND", "postgres_pgvector")
    monkeypatch.setenv("RAG_PGVECTOR_CAPABILITY_VERIFIED", "true")
    monkeypatch.setenv("RAG_PGVECTOR_DATABASE_URL", url)
    monkeypatch.setenv("RAG_PGVECTOR_FALLBACK_TO_SQLITE", "false")
    result = semantic_search("경로 검증", _EmbeddingClient(), model, limit=1)
    assert result[0]["id"] == passage_id
    assert result[0]["reference"] == "경로 1:1"

    with adapter.transaction() as connection:
        connection.execute("DELETE FROM rag_pgvector_embeddings WHERE passage_id=%s", (passage_id,))
        connection.execute("DELETE FROM rag_pgvector_passages WHERE id=%s", (passage_id,))
