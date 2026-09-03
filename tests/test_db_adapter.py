import uuid

import pytest

from app.db_adapter import DatabaseConfigurationError, ObjectStorageRecordRepository, create_database_adapter


def _record():
    return {
        "id": str(uuid.uuid4()), "document_id": None, "bucket_name": "test-bucket",
        "object_key": "_verification/adapter.txt", "version_id": None, "sha256": "a" * 64,
        "content_type": "text/plain", "size_bytes": 3, "original_filename": "adapter.txt",
        "upload_status": "VERIFIED",
    }


def _make_sqlite_table(adapter):
    with adapter.transaction() as con:
        con.execute("""CREATE TABLE object_storage_records (
            id TEXT PRIMARY KEY, document_id INTEGER, bucket_name TEXT NOT NULL,
            object_key TEXT NOT NULL, version_id TEXT, sha256 TEXT NOT NULL,
            content_type TEXT, size_bytes INTEGER NOT NULL, original_filename TEXT,
            upload_status TEXT NOT NULL)""")


def test_backend_selection_rejects_unknown_and_missing_postgres_url():
    with pytest.raises(DatabaseConfigurationError):
        create_database_adapter(database_path=":memory:", environ={"DB_BACKEND": "other"})
    with pytest.raises(DatabaseConfigurationError):
        create_database_adapter(environ={"DB_BACKEND": "postgres"})


def test_existing_adapter_crud_and_transaction_rollback(tmp_path):
    adapter = create_database_adapter(database_path=tmp_path / "adapter.sqlite3", environ={"DB_BACKEND": "existing"})
    _make_sqlite_table(adapter)
    repository = ObjectStorageRecordRepository(adapter)
    record = _record()
    assert repository.create(record)["object_key"] == record["object_key"]
    assert repository.get(record["id"])["sha256"] == record["sha256"]
    with pytest.raises(RuntimeError):
        with adapter.transaction() as con:
            con.execute("UPDATE object_storage_records SET upload_status=? WHERE id=?", ("FAILED", record["id"]))
            raise RuntimeError("test rollback")
    assert repository.get(record["id"])["upload_status"] == "VERIFIED"

