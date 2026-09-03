import datetime
import os

import pytest

from app.db_adapter import DatabaseTransientError, create_database_adapter, translate_database_error
from app.doctrine_repository_contract import DoctrineRepository


pytestmark = pytest.mark.integration


def test_postgres_boundary_values_jsonb_and_statement_timeout():
    if os.environ.get("RUN_DOCTRINE_BOUNDARIES") != "1":
        pytest.skip("명시적 doctrine boundary 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("RESTORED_DATABASE_URL", "")
    if "sermon_db_restore_test_v2" not in url or "sermon_db" in url.replace("sermon_db_restore_test_v2", ""):
        pytest.fail("boundary 시험은 sermon_db_restore_test_v2로 제한됩니다.")
    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    with adapter.transaction() as con:
        repo = DoctrineRepository(adapter)
        fixture = repo.create_fixture(con)
        document_id = con.execute("SELECT id FROM doctrine_documents WHERE object_storage_key=%s",
                                  ("_verification/adapter-compare.txt",)).fetchone()["id"]
        metadata = {"source": "fixture", "schema_version": 2, "nested": {"reviewed": False}}
        repo.set_document_metadata(con, document_id, metadata)
        assert repo.get_document_metadata(con, document_id) == metadata
        created_at = con.execute("SELECT created_at FROM doctrine_documents WHERE id=%s", (document_id,)).fetchone()["created_at"]
        assert isinstance(created_at, datetime.datetime) and created_at.tzinfo is not None
        con.execute("SET LOCAL statement_timeout='200ms'")
        with pytest.raises(Exception) as timeout:
            con.execute("SELECT pg_sleep(1)")
        translated = translate_database_error(timeout.value)
        assert isinstance(translated, DatabaseTransientError)
        assert translated.kind == "query_timeout"
        con.rollback()
