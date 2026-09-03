import os
import uuid

import pytest

from app.db_adapter import ObjectStorageRecordRepository, create_database_adapter


pytestmark = pytest.mark.integration


def test_postgres_object_storage_crud_and_rollback():
    if os.environ.get("RUN_POSTGRES_INTEGRATION") != "1":
        pytest.skip("명시적 테스트 DB 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ["DATABASE_URL"]
    if "sermon_db_test" not in url or "sermon_db" in url.replace("sermon_db_test", ""):
        pytest.fail("통합시험 대상은 sermon_db_test로 제한됩니다.")
    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    repository = ObjectStorageRecordRepository(adapter)
    record = {
        "id": str(uuid.uuid4()), "document_id": None, "bucket_name": "sermon-documents-test",
        "object_key": "_verification/adapter-integration.txt", "version_id": None,
        "sha256": "b" * 64, "content_type": "text/plain", "size_bytes": 4,
        "original_filename": "adapter-integration.txt", "upload_status": "VERIFIED",
    }
    created = repository.create(record)
    assert created["bucket_name"] == record["bucket_name"]
    with pytest.raises(RuntimeError):
        with adapter.transaction() as con:
            con.execute("UPDATE object_storage_records SET upload_status=%s WHERE id=%s", ("FAILED", record["id"]))
            raise RuntimeError("test rollback")
    assert repository.get(record["id"])["upload_status"] == "VERIFIED"
    with adapter.transaction() as con:
        con.execute("DELETE FROM object_storage_records WHERE id=%s", (record["id"],))
