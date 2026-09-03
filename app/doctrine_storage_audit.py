"""Read-only DB/MinIO reference checks for source snapshot recovery."""

from __future__ import annotations

from collections.abc import Iterable

from app.doctrine_storage import MinioObjectStore


def audit_minio_references(
    store: MinioObjectStore,
    referenced_keys: Iterable[str],
    prefix: str = "production/",
) -> dict[str, list[str]]:
    """Report remote orphans and missing objects without deleting anything."""
    normalized_prefix = prefix.strip("/") + "/"
    expected = set()
    for key in referenced_keys:
        clean_key = str(key or "").lstrip("/")
        if not clean_key:
            continue
        remote_key = normalized_prefix + clean_key
        expected.add(remote_key)
        expected.add(remote_key.rsplit("/", 1)[0] + "/metadata.json")
    actual = set(store.list_keys(normalized_prefix))
    return {
        "orphan_objects": sorted(actual - expected),
        "missing_objects": sorted(expected - actual),
    }
