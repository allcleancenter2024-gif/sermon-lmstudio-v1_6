import datetime
import sqlite3
import uuid
import psycopg.errors

from app.db_adapter import DatabaseTransientError, ObjectStorageRecordRepository, create_database_adapter, translate_database_error
from app.doctrine_repository_contract import DoctrineRepository


def test_uuid_timestamp_and_json_schema_extension_round_trip(tmp_path):
    adapter = create_database_adapter(database_path=tmp_path / "boundary.sqlite3", environ={"DB_BACKEND": "existing"})
    record_id = str(uuid.uuid4())
    with adapter.transaction() as con:
        con.execute("""CREATE TABLE object_storage_records (
            id TEXT PRIMARY KEY, document_id INTEGER, bucket_name TEXT NOT NULL,
            object_key TEXT NOT NULL, version_id TEXT, sha256 TEXT NOT NULL,
            content_type TEXT, size_bytes INTEGER NOT NULL, original_filename TEXT,
            upload_status TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        ObjectStorageRecordRepository(adapter).create({
            "id": record_id, "document_id": None, "bucket_name": "sermon-documents-test",
            "object_key": "_verification/boundary/uuid.txt", "version_id": None,
            "sha256": "d" * 64, "content_type": "text/plain", "size_bytes": 1,
            "original_filename": "uuid.txt", "upload_status": "VERIFIED",
        })
        con.execute("UPDATE object_storage_records SET created_at=? WHERE id=?",
                     (datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc).isoformat(), record_id))
        assert ObjectStorageRecordRepository(adapter).get(record_id)["id"] == record_id
        repo = DoctrineRepository(adapter)
        repo.ensure_sqlite_tables(con)
        repo.create_fixture(con)
        document_id = con.execute("SELECT id FROM doctrine_documents WHERE object_storage_key=?",
                                  ("_verification/adapter-compare.txt",)).fetchone()[0]
        expanded = {"source": "fixture", "verified": True, "schema_version": 2,
                    "labels": ["doctrine", "test"], "nested": {"reviewed": False}}
        repo.set_document_metadata(con, document_id, expanded)
        assert repo.get_document_metadata(con, document_id) == expanded


def test_transient_postgres_errors_have_retryable_kinds():
    assert translate_database_error(psycopg.errors.DeadlockDetected()).kind == "deadlock"
    assert translate_database_error(psycopg.errors.LockNotAvailable()).kind == "lock_timeout"
    assert isinstance(translate_database_error(psycopg.errors.QueryCanceled()), DatabaseTransientError)
