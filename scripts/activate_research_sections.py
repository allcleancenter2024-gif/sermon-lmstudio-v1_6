"""Back up, validate, and explicitly activate the Research Section schema."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backup import create_backup, inspect_backup, restore_backup
from app.migrations import RESEARCH_SECTIONS_MIGRATION_ID, apply_research_sections_migration


CRITICAL_TABLES = (
    "passages", "sermons", "sermon_versions", "generation_audits",
    "sermon_reviews", "sermon_version_locks",
)


def _counts(con: sqlite3.Connection) -> dict[str, int]:
    existing = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {name: int(con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]) for name in CRITICAL_TABLES if name in existing}


def _state(db_path: Path) -> dict:
    with closing(sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)) as con:
        return {
            "counts": _counts(con),
            "quick_check": str(con.execute("PRAGMA quick_check").fetchone()[0]),
            "canary_table": bool(con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sermon_sections'"
            ).fetchone()),
            "migration_recorded": bool(
                con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
                and con.execute(
                    "SELECT 1 FROM schema_migrations WHERE migration_id=?", (RESEARCH_SECTIONS_MIGRATION_ID,)
                ).fetchone()
            ),
        }


def activate(
    db_path: Path,
    backups_dir: Path,
    app_version: str,
    *,
    apply_migration: Callable[[Path], dict] = apply_research_sections_migration,
) -> dict:
    db_path, backups_dir = Path(db_path), Path(backups_dir)
    if os.getenv("RESEARCH_SECTION_CANARY", "false").strip().lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("migration 중에는 RESEARCH_SECTION_CANARY를 OFF로 유지해야 합니다.")
    before = _state(db_path)
    if before["canary_table"] or before["migration_recorded"]:
        if before["canary_table"] and before["migration_recorded"] and before["quick_check"] == "ok":
            return {"ok": True, "already_applied": True, "before": before, "after": before}
        raise RuntimeError("Research Section schema가 부분 적용된 상태입니다. 자동 진행을 중단합니다.")

    backup = create_backup(db_path, backups_dir, app_version, reason="pre_research_sections_canary")
    backup_path = backups_dir / backup["filename"]
    inspected = inspect_backup(backup_path)
    if not inspected["ok"]:
        raise RuntimeError("migration 전 백업 검증에 실패했습니다.")

    restored = False
    try:
        migration = apply_migration(db_path)
        after = _state(db_path)
        if after["quick_check"] != "ok":
            raise RuntimeError(f"migration 후 SQLite 무결성 오류: {after['quick_check']}")
        if before["counts"] != after["counts"]:
            raise RuntimeError("migration 후 기존 핵심 테이블 row count가 변경되었습니다.")
        if not after["canary_table"] or not after["migration_recorded"]:
            raise RuntimeError("Research Section migration 완료 표식이 불완전합니다.")
    except Exception:
        restore_backup(backup_path, db_path, backups_dir, app_version)
        restored = True
        recovered = _state(db_path)
        if recovered["quick_check"] != "ok" or recovered["counts"] != before["counts"]:
            raise RuntimeError("migration 실패 후 백업 자동 복원 검증에도 실패했습니다.")
        raise

    return {
        "ok": True,
        "already_applied": False,
        "backup": backup,
        "backup_inspection": inspected,
        "migration": migration,
        "before": before,
        "after": after,
        "auto_restored": restored,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--backups", type=Path, required=True)
    parser.add_argument("--app-version", required=True)
    args = parser.parse_args()
    result = activate(args.database, args.backups, args.app_version)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
