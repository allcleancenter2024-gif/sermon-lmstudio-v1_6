"""Rehearse the Research Canary activation gate without changing production state."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.migrations import RESEARCH_SECTIONS_MIGRATION_ID
from scripts.rehearse_research_sections import rehearse


def _state(database: Path) -> dict:
    with closing(sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True)) as con:
        return {
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


def rehearse_activation(database: Path) -> dict:
    database = Path(database).resolve()
    if os.getenv("RESEARCH_SECTION_CANARY", "false").strip().lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("rehearsal 중에는 RESEARCH_SECTION_CANARY를 OFF로 유지해야 합니다.")
    state = _state(database)
    if state["canary_table"] or state["migration_recorded"]:
        valid = state["canary_table"] and state["migration_recorded"] and state["quick_check"] == "ok"
        return {
            "ok": valid,
            "mode": "schema_already_activated",
            "activation_performed": False,
            "source_unchanged": True,
            "state": state,
            "steps": ["feature flag OFF 확인", "Schema 상태 읽기 검증", "활성화 명령 미실행", "rollback 명령 미실행"],
        }
    rehearsal = rehearse(database)
    return {
        "ok": bool(rehearsal["ok"]),
        "mode": "disposable_clone",
        "activation_performed": False,
        "source_unchanged": rehearsal["source_unchanged"],
        "migration_rehearsal": rehearsal,
        "steps": ["feature flag OFF 확인", "백업 후 migration 계획 확인", "disposable clone migration", "실패 시 백업 복원 계획 확인"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    result = rehearse_activation(args.database)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
