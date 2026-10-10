"""Rehearse the Research Section migration on a disposable SQLite clone."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.migrations import RESEARCH_SECTIONS_MIGRATION_ID, apply_research_sections_migration


CRITICAL_TABLES = (
    "passages",
    "sermons",
    "sermon_versions",
    "generation_audits",
    "sermon_reviews",
    "sermon_version_locks",
)


def _schema_signature(con: sqlite3.Connection, excluded: set[str] | None = None) -> str:
    excluded = excluded or set()
    rows = con.execute(
        "SELECT type, name, tbl_name, COALESCE(sql, '') FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    payload = "\n".join("|".join(map(str, row)) for row in rows if row[1] not in excluded)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _counts(con: sqlite3.Connection) -> dict[str, int]:
    existing = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in CRITICAL_TABLES if table in existing}


def rehearse(source: Path) -> dict:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    source_uri = f"file:{source.as_posix()}?mode=ro"
    source_stat = source.stat()
    with tempfile.TemporaryDirectory(prefix="sermon-research-rehearsal-") as directory:
        clone = Path(directory) / "bible-rehearsal.db"
        with closing(sqlite3.connect(source_uri, uri=True)) as source_con:
            source_counts = _counts(source_con)
            source_schema = _schema_signature(source_con)
            source_has_canary = bool(source_con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sermon_sections'"
            ).fetchone())
            with closing(sqlite3.connect(clone)) as clone_con:
                source_con.backup(clone_con)
        result = apply_research_sections_migration(clone)
        with closing(sqlite3.connect(clone)) as clone_con:
            clone_counts = _counts(clone_con)
            clone_integrity = clone_con.execute("PRAGMA quick_check").fetchone()[0]
            migration_recorded = bool(clone_con.execute(
                "SELECT 1 FROM schema_migrations WHERE migration_id=?", (RESEARCH_SECTIONS_MIGRATION_ID,)
            ).fetchone())
            clone_schema_without_canary = _schema_signature(
                clone_con,
                {"sermon_sections", "idx_sermon_sections_project_type", "idx_sermon_sections_status"},
            )
        unchanged = source.stat().st_size == source_stat.st_size and source.stat().st_mtime_ns == source_stat.st_mtime_ns
        return {
            "source": str(source),
            "source_unchanged": unchanged,
            "source_has_canary": source_has_canary,
            "migration": result,
            "migration_recorded_on_clone": migration_recorded,
            "critical_counts_preserved": source_counts == clone_counts,
            "source_counts": source_counts,
            "clone_counts": clone_counts,
            "legacy_schema_preserved": source_schema == clone_schema_without_canary,
            "clone_quick_check": clone_integrity,
            "ok": bool(unchanged and not source_has_canary and migration_recorded and source_counts == clone_counts and source_schema == clone_schema_without_canary and clone_integrity == "ok"),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    result = rehearse(args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
