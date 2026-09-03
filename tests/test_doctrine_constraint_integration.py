import datetime
import os

import pytest

from app.db_adapter import DatabaseConstraintError, create_database_adapter
from app.doctrine_repository_contract import DoctrineRepository
from tests.test_doctrine_repository_contract import _Rollback


pytestmark = pytest.mark.integration


def test_postgres_timestamp_json_and_constraint_contract():
    if os.environ.get("RUN_DOCTRINE_CONSTRAINTS") != "1":
        pytest.skip("명시적 doctrine constraint 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("RESTORED_DATABASE_URL", "")
    if "sermon_db_restore_test_v2" not in url or "sermon_db" in url.replace("sermon_db_restore_test_v2", ""):
        pytest.fail("비교시험은 sermon_db_restore_test_v2로 제한됩니다.")
    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    try:
        with adapter.transaction() as con:
            repo = DoctrineRepository(adapter)
            repo.create_fixture(con)
            document_id = con.execute("SELECT id FROM doctrine_documents WHERE object_storage_key=%s", ("_verification/adapter-compare.txt",)).fetchone()["id"]
            repo.set_document_metadata(con, document_id, {"source": "fixture", "verified": True})
            assert repo.get_document_metadata(con, document_id) == {"source": "fixture", "verified": True}
            created_at = con.execute("SELECT created_at FROM doctrine_documents WHERE id=%s", (document_id,)).fetchone()["created_at"]
            assert isinstance(created_at, datetime.datetime)
            assert created_at.tzinfo is not None
            con.execute("SAVEPOINT duplicate_check")
            with pytest.raises(DatabaseConstraintError) as duplicate:
                repo.create_fixture(con)
            con.execute("ROLLBACK TO SAVEPOINT duplicate_check")
            con.execute("RELEASE SAVEPOINT duplicate_check")
            assert duplicate.value.kind == "unique"
            con.execute("SAVEPOINT foreign_key_check")
            with pytest.raises(DatabaseConstraintError) as foreign_key:
                repo.insert_invalid_source(con)
            con.execute("ROLLBACK TO SAVEPOINT foreign_key_check")
            con.execute("RELEASE SAVEPOINT foreign_key_check")
            assert foreign_key.value.kind == "foreign_key"
            raise _Rollback(None)
    except _Rollback:
        pass
