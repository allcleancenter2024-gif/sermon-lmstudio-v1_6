import os

import pytest

from app.doctrine_backend import create_doctrine_backend
from app.doctrine_processing import read_document_processing_metadata, write_document_processing_metadata
from tests.test_doctrine_repository_contract import _Rollback


pytestmark = pytest.mark.integration


def test_processing_metadata_reads_and_writes_through_postgres_factory():
    if os.environ.get("RUN_PROCESSING_BACKEND") != "1":
        pytest.skip("명시적 processing backend 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("RESTORED_DATABASE_URL", "")
    if "sermon_db_restore_test_v2" not in url or "sermon_db" in url.replace("sermon_db_restore_test_v2", ""):
        pytest.fail("processing backend 시험은 sermon_db_restore_test_v2로 제한됩니다.")
    backend = create_doctrine_backend(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    try:
        with backend.adapter.transaction() as con:
            backend.repository.create_fixture(con)
            document_id = con.execute("SELECT id FROM doctrine_documents WHERE object_storage_key=%s",
                                      ("_verification/adapter-compare.txt",)).fetchone()["id"]
            expected = {"quality": {"passed": True}, "backend": "postgres"}
            write_document_processing_metadata(document_id, expected, db_path=None, backend=backend, connection=con)
            assert read_document_processing_metadata(document_id, db_path=None, backend=backend, connection=con) == expected
            raise _Rollback(None)
    except _Rollback:
        pass
