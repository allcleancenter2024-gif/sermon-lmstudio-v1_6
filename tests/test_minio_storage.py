import hashlib
import os
from unittest.mock import Mock

import pytest

from app.doctrine_storage import MinioObjectStore


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self):
        return self.payload

    def close(self):
        pass

    def release_conn(self):
        pass


def test_minio_store_rejects_when_disabled(monkeypatch):
    monkeypatch.delenv("MINIO_ENABLED", raising=False)
    with pytest.raises(ValueError, match="MINIO_ENABLED"):
        MinioObjectStore.from_env()


def test_minio_store_preserves_matching_existing_object():
    payload = b"immutable source"
    digest = hashlib.sha256(payload).hexdigest()
    client = Mock()
    client.bucket_exists.return_value = True
    client.get_object.return_value = _Response(payload)
    store = MinioObjectStore("http://127.0.0.1:9000", "access", "secret", "sermon-documents", client=client)

    stored = store.put_bytes("_verification/source.bin", payload, digest)

    assert stored.size == len(payload)
    assert stored.sha256 == digest
    client.put_object.assert_not_called()


def test_minio_store_rejects_digest_mismatch_before_upload():
    client = Mock()
    store = MinioObjectStore("http://127.0.0.1:9000", "access", "secret", "sermon-documents", client=client)

    with pytest.raises(ValueError, match="SHA-256"):
        store.put_bytes("_verification/source.bin", b"payload", "0" * 64)

    client.bucket_exists.assert_not_called()
    client.put_object.assert_not_called()
