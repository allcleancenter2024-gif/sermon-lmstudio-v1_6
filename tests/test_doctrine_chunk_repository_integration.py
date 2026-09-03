import os

import pytest

from app.doctrine_backend import create_doctrine_backend
from tests.test_doctrine_repository_contract import _Rollback


pytestmark = pytest.mark.integration


def test_postgres_chunk_replace_and_read_rolls_back():
    if os.environ.get("RUN_CHUNK_REPOSITORY") != "1":
        pytest.skip("명시적 chunk repository 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("RESTORED_DATABASE_URL", "")
    if "sermon_db_restore_test_v2" not in url or "sermon_db" in url.replace("sermon_db_restore_test_v2", ""):
        pytest.fail("chunk 시험은 sermon_db_restore_test_v2로 제한됩니다.")
    backend = create_doctrine_backend(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    try:
        with backend.adapter.transaction() as con:
            backend.repository.create_fixture(con)
            document_id = con.execute("SELECT id FROM doctrine_documents WHERE object_storage_key=%s",
                                      ("_verification/adapter-compare.txt",)).fetchone()["id"]
            chunks = [{"section_path": "제1조", "article_number": "1", "article_title": "고백",
                       "chunk_index": 0, "content": "첫 번째 chunk", "token_count": 2,
                       "scripture_refs": ["John 3:16"], "topic_tags": ["love"], "content_hash": "e" * 64},
                      {"section_path": "제1조", "article_number": "1", "article_title": "고백",
                       "chunk_index": 1, "content": "두 번째 chunk", "token_count": 2,
                       "scripture_refs": [], "topic_tags": ["faith"], "content_hash": "f" * 64}]
            assert backend.chunk_repository.replace_chunks(con, document_id, chunks) == 2
            assert backend.chunk_repository.list_chunks(con, document_id) == [
                dict({"document_id": document_id}, **chunk) for chunk in chunks
            ]
            raise _Rollback(None)
    except _Rollback:
        pass
