"""Read-only pre-cutover readiness audit for isolated test environments."""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

from app.schema_drift_audit import audit_schema


def audit_test_readiness(
    adapter,
    manifest: dict[str, Any],
    *,
    minio_config: dict[str, str],
    minio_probe: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Return a safe checklist; never writes DB or object storage."""
    with adapter.transaction() as con:
        identity = con.execute("SELECT current_database() AS database_name, current_user AS user_name").fetchone()
    database_name = identity["database_name"]
    database_ok = database_name.endswith("_test") or "_test_" in database_name
    schema = audit_schema(adapter, manifest)

    endpoint = minio_config.get("endpoint", "").strip()
    parsed = urlparse(endpoint)
    endpoint_ok = parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"}
    bucket = minio_config.get("bucket", "").strip()
    bucket_ok = bucket.endswith("-test") or bucket.endswith("_test")
    prefix = minio_config.get("test_prefix", "")
    prefix_ok = bool(prefix) and not prefix.startswith("/") and prefix.endswith("/") and prefix == "_verification/"
    credentials_ok = bool(minio_config.get("access_key", "").strip()) and bool(minio_config.get("secret_key", "").strip())
    probe_ok = None
    if minio_probe is not None:
        try:
            minio_probe()
            probe_ok = True
        except Exception:
            probe_ok = False

    checks = {
        "database_is_test": database_ok,
        "schema_manifest": schema["status"] == "PASS",
        "minio_endpoint_is_localhost": endpoint_ok,
        "minio_bucket_is_test": bucket_ok,
        "minio_prefix_is_verification": prefix_ok,
        "minio_credentials_present": credentials_ok,
    }
    if probe_ok is not None:
        checks["minio_read_probe"] = probe_ok
    return {
        "status": "PASS" if all(checks.values()) else "NOT_READY",
        "database": database_name,
        "database_user": identity["user_name"],
        "checks": checks,
        "schema": schema,
        "minio_probe": probe_ok,
    }
