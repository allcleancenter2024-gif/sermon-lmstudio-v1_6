"""SQLite repository for immutable, versioned research Sections."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.application.research_persistence_contracts import ResearchSectionRecord


def _decode(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["content"] = json.loads(item.pop("content_json"))
    return item


class ResearchSectionRepository:
    """Persist new versions without updating or deleting prior versions."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        if not self._table_exists(con):
            con.close()
            raise RuntimeError("sermon_sections migration is required")
        return con

    @staticmethod
    def _table_exists(con: sqlite3.Connection) -> bool:
        return bool(con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sermon_sections'"
        ).fetchone())

    def require_ready(self) -> None:
        """Fail before a Builder runs when the explicit migration is absent."""
        if not self.db_path.is_file():
            raise RuntimeError("sermon_sections migration is required")
        with closing(sqlite3.connect(f"file:{self.db_path.resolve().as_posix()}?mode=ro", uri=True)) as con:
            if not self._table_exists(con):
                raise RuntimeError("sermon_sections migration is required")

    def create_version(
        self,
        *,
        project_id: int,
        section_type: str,
        status: str,
        content: dict[str, Any],
        source_coverage: float = 0.0,
        quality_status: str = "not_checked",
        review_status: str = "unreviewed",
        source_snapshot_id: str = "",
    ) -> dict[str, Any]:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as con:
            try:
                con.execute("BEGIN IMMEDIATE")
                version = int(
                    con.execute(
                        "SELECT COALESCE(MAX(version), 0) + 1 FROM sermon_sections "
                        "WHERE project_id=? AND section_type=?",
                        (project_id, section_type.strip()),
                    ).fetchone()[0]
                )
                record = ResearchSectionRecord(
                    project_id=project_id,
                    section_type=section_type.strip(),
                    version=version,
                    status=status,
                    content=dict(content),
                    source_coverage=source_coverage,
                    quality_status=quality_status,
                    review_status=review_status,
                    source_snapshot_id=source_snapshot_id.strip(),
                )
                errors = record.validate()
                if errors:
                    raise ValueError("; ".join(errors))
                cursor = con.execute(
                    """INSERT INTO sermon_sections(
                           project_id, section_type, version, status, content_json,
                           source_coverage, quality_status, review_status,
                           source_snapshot_id, created_at, updated_at
                       ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.project_id,
                        record.section_type,
                        record.version,
                        record.status,
                        json.dumps(record.content, ensure_ascii=False, sort_keys=True),
                        record.source_coverage,
                        record.quality_status,
                        record.review_status,
                        record.source_snapshot_id,
                        now,
                        now,
                    ),
                )
                row_id = int(cursor.lastrowid)
                con.commit()
            except Exception:
                con.rollback()
                raise
        result = self.get(row_id)
        if result is None:  # pragma: no cover - committed row invariant
            raise RuntimeError("saved research section could not be reloaded")
        return result

    def get(self, row_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT * FROM sermon_sections WHERE id=?", (row_id,)
            ).fetchone()
        return _decode(row) if row else None

    def list_versions(self, project_id: int, section_type: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT * FROM sermon_sections WHERE project_id=? AND section_type=? "
                "ORDER BY version DESC",
                (project_id, section_type.strip()),
            ).fetchall()
        return [_decode(row) for row in rows]

    def latest(self, project_id: int, section_type: str) -> dict[str, Any] | None:
        versions = self.list_versions(project_id, section_type)
        return versions[0] if versions else None


__all__ = ["ResearchSectionRepository"]
