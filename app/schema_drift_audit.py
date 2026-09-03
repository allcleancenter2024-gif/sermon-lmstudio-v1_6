"""Read-only schema drift audit for the isolated PostgreSQL rehearsal."""

from __future__ import annotations

from typing import Any


def audit_schema(adapter, manifest: dict[str, Any]) -> dict[str, Any]:
    """Compare a live schema with a manifest without creating or changing anything."""
    if adapter.backend != "postgres":
        raise ValueError("schema drift audit는 PostgreSQL adapter만 지원합니다.")
    expected_tables = set(manifest.get("required_tables", []))
    expected_extensions = set(manifest.get("required_extensions", []))
    with adapter.transaction() as con:
        tables = {row["table_name"] for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ).fetchall()}
        extensions = {row["extname"] for row in con.execute(
            "SELECT extname FROM pg_extension"
        ).fetchall()}
        version_row = None
        if "schema_versions" in tables:
            version_row = con.execute(
                "SELECT version, migration_id FROM schema_versions ORDER BY version DESC LIMIT 1"
            ).fetchone()
    missing_tables = sorted(expected_tables - tables)
    missing_extensions = sorted(expected_extensions - extensions)
    version_ok = bool(version_row and version_row["version"] == manifest.get("version") and
                      version_row["migration_id"] == manifest.get("migration_id"))
    return {
        "status": "PASS" if not missing_tables and not missing_extensions and version_ok else "DRIFT",
        "missing_tables": missing_tables,
        "missing_extensions": missing_extensions,
        "version_match": version_ok,
        "recorded_version": dict(version_row) if version_row else None,
    }
