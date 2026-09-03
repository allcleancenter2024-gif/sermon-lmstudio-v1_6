import hashlib
import os
import uuid

import pytest

from app.db_adapter import ObjectStorageRecordRepository, create_database_adapter
from app.doctrine_storage import MinioObjectStore


pytestmark = pytest.mark.integration


def test_minio_object_metadata_matches_postgres_record():
    if os.environ.get("RUN_MINIO_DB_INTEGRATION") != "1":
        pytest.skip("명시적 MinIO·PostgreSQL 통합시험 플래그가 없어 건너뜁니다.")
    required = ("DATABASE_URL", "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        pytest.fail("통합시험 필수 환경변수가 없습니다: " + ", ".join(missing))
    database_url = os.environ["DATABASE_URL"]
    bucket = os.environ["MINIO_BUCKET"]
    if "sermon_db_test" not in database_url or bucket != "sermon-documents-test":
        pytest.fail("통합시험은 sermon_db_test와 sermon-documents-test로 제한됩니다.")
    store = MinioObjectStore.from_env()
    payload = b"adapter minio metadata integration"
    key = "_verification/adapter-db/" + uuid.uuid4().hex + ".txt"
    digest = hashlib.sha256(payload).hexdigest()
    stored = store.put_bytes(key, payload, digest)
    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": database_url})
    repository = ObjectStorageRecordRepository(adapter)
    record = {
        "id": str(uuid.uuid4()), "document_id": None, "bucket_name": bucket,
        "object_key": stored.key, "version_id": stored.version_id, "sha256": stored.sha256,
        "content_type": "text/plain", "size_bytes": stored.size,
        "original_filename": "adapter-metadata.txt", "upload_status": "VERIFIED",
    }
    saved = repository.create(record)
    assert saved["object_key"] == key
    assert saved["sha256"] == digest
    assert saved["size_bytes"] == len(payload)
    assert saved["version_id"] == stored.version_id
