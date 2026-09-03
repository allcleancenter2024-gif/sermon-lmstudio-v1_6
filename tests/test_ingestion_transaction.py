import hashlib

from app.db_adapter import ObjectStorageRecordRepository, create_database_adapter
from app.doctrine_storage import StoredObject
from app.ingestion_transaction import upload_and_record


class _Store:
    def __init__(self, fail=False, error=OSError("storage unavailable")):
        self.fail = fail
        self.error = error
        self.calls = []

    def put_bytes(self, key, payload, sha256):
        self.calls.append((key, payload, sha256))
        if self.fail:
            raise self.error
        return StoredObject(key, len(payload), sha256, None)


class _FailingRepository:
    def create(self, _record):
        raise RuntimeError("database unavailable")


def _repo(tmp_path):
    adapter = create_database_adapter(database_path=tmp_path / "adapter.sqlite3", environ={"DB_BACKEND": "existing"})
    with adapter.transaction() as con:
        con.execute("""CREATE TABLE object_storage_records (
            id TEXT PRIMARY KEY, document_id INTEGER, bucket_name TEXT NOT NULL,
            object_key TEXT NOT NULL, version_id TEXT, sha256 TEXT NOT NULL,
            content_type TEXT, size_bytes INTEGER NOT NULL, original_filename TEXT,
            upload_status TEXT NOT NULL)""")
    return adapter, ObjectStorageRecordRepository(adapter)


def test_success_records_verified_object(tmp_path):
    adapter, repository = _repo(tmp_path)
    payload = b"safe test object"
    result = upload_and_record(_Store(), repository, key="_verification/run/object.txt", payload=payload,
                               bucket_name="sermon-documents-test", original_filename="object.txt")
    assert result["status"] == "VERIFIED"
    assert result["record"]["sha256"] == hashlib.sha256(payload).hexdigest()


def test_retry_reuses_existing_record_without_duplicate(tmp_path):
    adapter, repository = _repo(tmp_path)
    store = _Store()
    kwargs = dict(key="_verification/run/idempotent.txt", payload=b"same object",
                  bucket_name="sermon-documents-test", original_filename="idempotent.txt")
    first = upload_and_record(store, repository, **kwargs)
    second = upload_and_record(store, repository, **kwargs)
    assert first["status"] == "VERIFIED"
    assert second["status"] == "RETRY_REUSED"
    with adapter.transaction() as con:
        assert con.execute("SELECT COUNT(*) FROM object_storage_records").fetchone()[0] == 1


def test_database_failure_reports_orphan_candidate_without_delete():
    store = _Store()
    result = upload_and_record(store, _FailingRepository(), key="_verification/run/orphan.txt",
                               payload=b"orphan candidate", bucket_name="sermon-documents-test",
                               original_filename="orphan.txt")
    assert result["status"] == "DB_FAILED"
    assert result["orphan_candidate"] is True
    assert len(store.calls) == 1


def test_storage_failure_does_not_attempt_database_record(tmp_path):
    _adapter, repository = _repo(tmp_path)
    result = upload_and_record(_Store(fail=True), repository, key="_verification/run/fail.txt",
                               payload=b"not stored", bucket_name="sermon-documents-test",
                               original_filename="fail.txt")
    assert result == {"status": "STORAGE_FAILED", "db_recorded": False,
                      "orphan_candidate": False, "error_type": "OSError"}


def test_timeout_is_reported_as_storage_failure(tmp_path):
    _adapter, repository = _repo(tmp_path)
    result = upload_and_record(_Store(fail=True, error=TimeoutError("timed out")), repository,
                               key="_verification/run/timeout.txt", payload=b"timeout",
                               bucket_name="sermon-documents-test", original_filename="timeout.txt")
    assert result["status"] == "STORAGE_FAILED"
    assert result["error_type"] == "TimeoutError"


def test_new_adapter_instance_can_reconnect_and_read_record(tmp_path):
    db_path = tmp_path / "adapter.sqlite3"
    adapter, repository = _repo(tmp_path)
    result = upload_and_record(_Store(), repository, key="_verification/run/restart.txt", payload=b"restart",
                               bucket_name="sermon-documents-test", original_filename="restart.txt")
    record_id = result["record"]["id"]
    reopened = create_database_adapter(database_path=db_path, environ={"DB_BACKEND": "existing"})
    assert ObjectStorageRecordRepository(reopened).get(record_id)["upload_status"] == "VERIFIED"
