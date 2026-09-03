"""Explicit schema-version recording for the PostgreSQL dry-run only.

Nothing calls this module during application startup.  The migration runner or
an operator must invoke it explicitly after a tested schema change.
"""

from __future__ import annotations

from typing import Any


SCHEMA_VERSION_TABLE = "schema_versions"


def _placeholder(adapter) -> str:
    return "?" if adapter.backend == "existing" else "%s"


def ensure_schema_version_table(adapter) -> None:
    with adapter.transaction() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            migration_id TEXT NOT NULL UNIQUE,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")


def record_schema_version(adapter, version: int, migration_id: str) -> dict[str, Any]:
    """Record one idempotent version; never silently changes an existing ID."""
    if version < 1 or not migration_id.strip():
        raise ValueError("schema version과 migration_id가 필요합니다.")
    ensure_schema_version_table(adapter)
    placeholder = _placeholder(adapter)
    with adapter.transaction() as con:
        row = con.execute(
            f"SELECT version, migration_id, applied_at FROM schema_versions WHERE version={placeholder}",
            (version,),
        ).fetchone()
        if row is not None:
            existing = dict(row) if isinstance(row, dict) else dict(row)
            if existing["migration_id"] != migration_id:
                raise ValueError("schema version에 다른 migration_id가 이미 기록되어 있습니다.")
            return existing
        con.execute(
            f"INSERT INTO schema_versions(version, migration_id) VALUES({placeholder}, {placeholder})",
            (version, migration_id.strip()),
        )
        row = con.execute(
            f"SELECT version, migration_id, applied_at FROM schema_versions WHERE version={placeholder}",
            (version,),
        ).fetchone()
    return dict(row) if isinstance(row, dict) else dict(row)


def latest_schema_version(adapter) -> dict[str, Any] | None:
    ensure_schema_version_table(adapter)
    with adapter.transaction() as con:
        row = con.execute(
            "SELECT version, migration_id, applied_at FROM schema_versions ORDER BY version DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return dict(row) if isinstance(row, dict) else dict(row)

