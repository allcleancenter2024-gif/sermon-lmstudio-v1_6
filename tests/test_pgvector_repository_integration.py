import os
import uuid

import pytest

from app.db_adapter import create_database_adapter
from app.rag.pgvector import MODEL_DIMENSION, PgVectorRagRepository


pytestmark = pytest.mark.integration


def test_pgvector_repository_crud_search_and_rollback():
    if os.environ.get("RUN_PGVECTOR_REPOSITORY_INTEGRATION") != "1":
        pytest.skip("명시적 pgvector Repository 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("PGVECTOR_DATABASE_URL", "")
    if "sermon_pgvector_test" not in url or "sermon_db" in url.replace("sermon_pgvector_test", ""):
        pytest.fail("통합시험 대상은 sermon_pgvector_test로 제한됩니다.")

    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    repository = PgVectorRagRepository(adapter)
    repository.ensure_schema()
    passage_id = 900000 + int(uuid.uuid4().int % 9999)
    model = "text-embedding-nomic-embed-text-v1.5"
    repository.upsert_passages([{"id": passage_id, "translation": "TEST", "language": "ko", "reference": "검증 1:1", "text": "검증 본문", "license_note": "test"}])
    vector = [1.0] + [0.0] * (MODEL_DIMENSION - 1)
    repository.upsert_embeddings([(passage_id, vector)], model)
    result = repository.search(vector, model, limit=1)
    assert result[0]["id"] == passage_id
    assert result[0]["semantic_score"] == pytest.approx(1.0, abs=1e-5)

    with pytest.raises(RuntimeError):
        with adapter.transaction() as connection:
            connection.execute("DELETE FROM rag_pgvector_passages WHERE id=%s", (passage_id,))
            raise RuntimeError("repository rollback")
    assert repository.search(vector, model, limit=1)[0]["id"] == passage_id

    with adapter.transaction() as connection:
        connection.execute("DELETE FROM rag_pgvector_embeddings WHERE passage_id=%s", (passage_id,))
        connection.execute("DELETE FROM rag_pgvector_passages WHERE id=%s", (passage_id,))
