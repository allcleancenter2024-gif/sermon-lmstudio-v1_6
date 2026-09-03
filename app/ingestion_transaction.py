"""Failure-aware object upload and metadata recording for the dry-run.

This coordinator is deliberately opt-in and does not replace the existing
SQLite ingestion flow.  It never deletes an object after a database failure;
the caller can send the returned orphan candidate to the read-only audit.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any


def upload_and_record(
    store,
    repository,
    *,
    key: str,
    payload: bytes,
    bucket_name: str,
    original_filename: str,
    content_type: str = "application/octet-stream",
    prefix: str = "_verification/",
) -> dict[str, Any]:
    """Upload one test-prefix object and record it without compensating delete."""
    if not prefix or prefix.startswith("/") or not prefix.endswith("/"):
        raise ValueError("검증 prefix는 앞에 /가 없고 마지막에 /가 있어야 합니다.")
    if not key.startswith(prefix) or key.startswith("/"):
        raise ValueError("객체 key가 허용된 검증 prefix 밖에 있습니다.")
    digest = hashlib.sha256(payload).hexdigest()
    try:
        stored = store.put_bytes(key, payload, digest)
    except Exception as exc:
        return {"status": "STORAGE_FAILED", "db_recorded": False, "orphan_candidate": False,
                "error_type": type(exc).__name__}
    record = {
        "id": str(uuid.uuid4()), "document_id": None, "bucket_name": bucket_name,
        "object_key": stored.key, "version_id": stored.version_id, "sha256": stored.sha256,
        "content_type": content_type, "size_bytes": stored.size,
        "original_filename": original_filename, "upload_status": "VERIFIED",
    }
    try:
        existing = repository.find_by_object(bucket_name, stored.key, stored.version_id)
        if existing is not None:
            if existing["sha256"] == stored.sha256 and int(existing["size_bytes"]) == stored.size:
                return {"status": "RETRY_REUSED", "db_recorded": True, "orphan_candidate": False,
                        "record": existing}
            return {"status": "DB_CONFLICT", "db_recorded": False, "orphan_candidate": True,
                    "object_key": stored.key, "version_id": stored.version_id,
                    "error_type": "ObjectMetadataConflict"}
        saved = repository.create(record)
    except Exception as exc:
        return {"status": "DB_FAILED", "db_recorded": False, "orphan_candidate": True,
                "object_key": stored.key, "version_id": stored.version_id,
                "error_type": type(exc).__name__}
    return {"status": "VERIFIED", "db_recorded": True, "orphan_candidate": False,
            "record": saved}
