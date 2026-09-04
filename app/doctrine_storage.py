"""Object storage boundary for Phase 2 source snapshots.

The production MinIO client is intentionally not configured here.  This
adapter keeps object persistence out of the ingestion transaction and gives
the next phase a compatible S3/MinIO seam without changing a bucket policy.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    sha256: str
    version_id: str | None = None


class LocalObjectStore:
    """Deterministic, immutable local store used when MinIO is not configured."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def put_file(self, key: str, source: Path, sha256: str) -> StoredObject:
        return self.put_bytes(key, Path(source).read_bytes(), sha256)

    def put_bytes(self, key: str, payload: bytes, sha256: str) -> StoredObject:
        """Store immutable bytes and verify the digest before returning."""
        actual = hashlib.sha256(payload).hexdigest()
        if actual != sha256:
            raise ValueError('저장 전 SHA-256 검증에 실패했습니다.')
        target = self.root / key.replace('/', '\\')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = hashlib.sha256(target.read_bytes()).hexdigest()
            if existing != sha256:
                raise ValueError('기존 객체와 SHA-256이 달라 덮어쓰기를 중단했습니다.')
            return StoredObject(key, target.stat().st_size, existing)
        target.write_bytes(payload)
        stored_digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if stored_digest != sha256:
            target.unlink(missing_ok=True)
            raise ValueError('저장 후 SHA-256 검증에 실패했습니다.')
        return StoredObject(key, target.stat().st_size, stored_digest)

    def exists(self, key: str) -> bool:
        return (self.root / key.replace('/', '\\')).is_file()

    def get_bytes(self, key: str) -> bytes:
        return (self.root / key.replace('/', '\\')).read_bytes()

    def verify(self, key: str, sha256: str) -> bool:
        target = self.root / key.replace('/', '\\')
        if not target.is_file():
            return False
        return hashlib.sha256(target.read_bytes()).hexdigest() == sha256

    def find_orphans(self, referenced_keys: Iterable[str]) -> list[str]:
        """Return archive files not referenced by the database; never deletes."""
        referenced = {str(key).replace('/', '\\') for key in referenced_keys if key}
        archive_root = self.root / 'doctrine-archive'
        if not archive_root.exists():
            return []
        return [
            str(path.relative_to(self.root)).replace('\\', '/')
            for path in archive_root.rglob('original.*')
            if str(path.relative_to(self.root)).replace('\\', '/') not in referenced
        ]


class MinioObjectStore:
    """Immutable MinIO mirror enabled explicitly through environment settings."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = False, client=None):
        from minio import Minio

        normalized = endpoint.strip().removesuffix('/')
        if normalized.startswith('http://'):
            normalized, secure = normalized[7:], False
        elif normalized.startswith('https://'):
            normalized, secure = normalized[8:], True
        if not normalized or '/' in normalized:
            raise ValueError('MINIO_ENDPOINT는 호스트와 포트만 포함해야 합니다.')
        if not access_key or not secret_key or not bucket:
            raise ValueError('MinIO 연결 설정이 완전하지 않습니다.')
        self.client = client or Minio(normalized, access_key=access_key, secret_key=secret_key, secure=secure)
        self.bucket = bucket

    @classmethod
    def from_env(cls) -> 'MinioObjectStore':
        enabled = os.getenv('MINIO_ENABLED', '').strip().casefold() in {'1', 'true', 'yes', 'on'}
        if not enabled:
            raise ValueError('MINIO_ENABLED가 활성화되지 않았습니다.')
        return cls(
            os.getenv('MINIO_ENDPOINT', 'http://127.0.0.1:9000'),
            os.getenv('MINIO_ACCESS_KEY', ''),
            os.getenv('MINIO_SECRET_KEY', ''),
            os.getenv('MINIO_BUCKET', 'sermon-documents'),
        )

    def put_bytes(self, key: str, payload: bytes, sha256: str) -> StoredObject:
        actual = hashlib.sha256(payload).hexdigest()
        if actual != sha256:
            raise ValueError('MinIO 저장 전 SHA-256 검증에 실패했습니다.')
        try:
            existing = self.client.get_object(self.bucket, key)
            try:
                existing_payload = existing.read()
            finally:
                existing.close()
                existing.release_conn()
            if hashlib.sha256(existing_payload).hexdigest() != sha256:
                raise ValueError('MinIO 기존 객체와 SHA-256이 달라 덮어쓰기를 중단했습니다.')
            return StoredObject(key, len(existing_payload), sha256, self._version_id(key))
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            from minio.error import S3Error
            if not isinstance(exc, S3Error) or exc.code not in {'NoSuchKey', 'NoSuchObject'}:
                raise
        self.client.put_object(self.bucket, key, io.BytesIO(payload), len(payload), content_type='application/octet-stream')
        stored = self.client.get_object(self.bucket, key)
        try:
            stored_payload = stored.read()
        finally:
            stored.close()
            stored.release_conn()
        stored_digest = hashlib.sha256(stored_payload).hexdigest()
        if stored_digest != sha256:
            raise ValueError('MinIO 저장 후 SHA-256 검증에 실패했습니다.')
        return StoredObject(key, len(stored_payload), stored_digest, self._version_id(key))

    def _version_id(self, key: str) -> str | None:
        """Read Versioning metadata without treating unversioned as an error."""
        try:
            version_id = self.client.stat_object(self.bucket, key).version_id
        except AttributeError:
            return None
        return version_id or None

    def list_keys(self, prefix: str = '') -> list[str]:
        """List object keys for audit purposes; never deletes or mutates objects."""
        return sorted(obj.object_name for obj in self.client.list_objects(self.bucket, prefix=prefix, recursive=True))

    def verify(self, key: str, sha256: str) -> bool:
        """Verify a remote object's bytes without mutating it."""
        try:
            response = self.client.get_object(self.bucket, key)
            try:
                payload = response.read()
            finally:
                response.close()
                response.release_conn()
        except Exception:
            return False
        return hashlib.sha256(payload).hexdigest() == sha256

    def exists(self, key: str) -> bool:
        """Check object existence without downloading or mutating it."""
        try:
            self.client.stat_object(self.bucket, key)
        except Exception:
            return False
        return True

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
