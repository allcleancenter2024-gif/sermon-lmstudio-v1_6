"""Persistence boundary for explicitly assigned sermon collaborators."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.application.collaboration_contracts import SermonAssignment


class SermonCollaborationRepository:
    """Store immutable assignment revisions after the gated schema exists."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        tables = {
            row[0]
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not {"sermon_collaboration_assignments", "sermon_collaboration_events"} <= tables:
            con.close()
            raise RuntimeError("sermon collaboration migration is required")
        return con

    def schema_ready(self) -> bool:
        try:
            with closing(self._connect()):
                return True
        except RuntimeError as exc:
            if "migration is required" in str(exc):
                return False
            raise

    def list_all_assignments(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT sermon_id, author_id, reviewer_id, approver_id, revision, assigned_by, created_at, updated_at "
                "FROM sermon_collaboration_assignments ORDER BY sermon_id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_assignment(self, sermon_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT sermon_id, author_id, reviewer_id, approver_id, revision, assigned_by, created_at, updated_at "
                "FROM sermon_collaboration_assignments WHERE sermon_id=?",
                (sermon_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT sermon_id, author_id, reviewer_id, approver_id, revision, assigned_by, created_at, updated_at "
                "FROM sermon_collaboration_assignments "
                "WHERE author_id=? OR reviewer_id=? OR approver_id=? ORDER BY sermon_id DESC",
                (user_id, user_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def assign(
        self,
        *,
        sermon_id: int,
        author_id: str,
        reviewer_id: str,
        approver_id: str,
        actor_id: str,
        expected_revision: int,
    ) -> dict[str, Any]:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        with closing(self._connect()) as con:
            try:
                con.execute("BEGIN IMMEDIATE")
                existing = con.execute(
                    "SELECT revision, author_id, reviewer_id, approver_id "
                    "FROM sermon_collaboration_assignments WHERE sermon_id=?",
                    (sermon_id,),
                ).fetchone()
                if not con.execute("SELECT 1 FROM sermons WHERE id=?", (sermon_id,)).fetchone():
                    raise ValueError("설교 프로젝트를 찾을 수 없습니다.")
                current_revision = int(existing["revision"]) if existing else 0
                if expected_revision != current_revision:
                    raise ValueError("expected_revision_mismatch")
                assignment = SermonAssignment(
                    sermon_id=sermon_id,
                    author_id=author_id,
                    reviewer_id=reviewer_id,
                    approver_id=approver_id,
                    revision=current_revision + 1,
                )
                errors = assignment.validate()
                if errors:
                    raise ValueError("; ".join(errors))
                if not actor_id.strip():
                    raise ValueError("actor_id is required")
                before = {
                    key: str(existing[key]) for key in ("author_id", "reviewer_id", "approver_id")
                } if existing else None
                con.execute(
                    """INSERT INTO sermon_collaboration_assignments(
                           sermon_id, author_id, reviewer_id, approver_id, revision,
                           assigned_by, created_at, updated_at
                       ) VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(sermon_id) DO UPDATE SET
                           author_id=excluded.author_id,
                           reviewer_id=excluded.reviewer_id,
                           approver_id=excluded.approver_id,
                           revision=excluded.revision,
                           assigned_by=excluded.assigned_by,
                           updated_at=excluded.updated_at""",
                    (
                        sermon_id, assignment.author_id.strip(), assignment.reviewer_id.strip(),
                        assignment.approver_id.strip(), assignment.revision, actor_id.strip(), now, now,
                    ),
                )
                con.execute(
                    """INSERT INTO sermon_collaboration_events(
                           sermon_id, assignment_revision, actor_id, action, details_json, created_at
                       ) VALUES(?,?,?,?,?,?)""",
                    (
                        sermon_id, assignment.revision, actor_id.strip(), "roles_assigned",
                        json.dumps({"before": before, "after": {
                            "author_id": assignment.author_id.strip(),
                            "reviewer_id": assignment.reviewer_id.strip(),
                            "approver_id": assignment.approver_id.strip(),
                        }}, ensure_ascii=False, sort_keys=True), now,
                    ),
                )
                result = dict(con.execute(
                    "SELECT sermon_id, author_id, reviewer_id, approver_id, revision, assigned_by, created_at, updated_at "
                    "FROM sermon_collaboration_assignments WHERE sermon_id=?",
                    (sermon_id,),
                ).fetchone())
                con.commit()
                return result
            except Exception:
                con.rollback()
                raise

    def list_assignment_events(self, sermon_id: int) -> list[dict[str, Any]]:
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT id, sermon_id, assignment_revision, actor_id, action, details_json, created_at "
                "FROM sermon_collaboration_events WHERE sermon_id=? ORDER BY id",
                (sermon_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result

    def record_workflow_event(
        self,
        *,
        sermon_id: int,
        assignment_revision: int,
        actor_id: str,
        action: str,
        version: int,
        status: str,
        review_created_at: str,
    ) -> dict[str, Any]:
        if action != "review_status" or version <= 0 or not actor_id.strip():
            raise ValueError("workflow event is invalid")
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        details = json.dumps(
            {"version": version, "status": status, "review_created_at": review_created_at},
            ensure_ascii=False,
            sort_keys=True,
        )
        with closing(self._connect()) as con:
            try:
                con.execute("BEGIN IMMEDIATE")
                current = con.execute(
                    "SELECT revision FROM sermon_collaboration_assignments WHERE sermon_id=?",
                    (sermon_id,),
                ).fetchone()
                if not current or int(current[0]) != assignment_revision:
                    raise ValueError("assignment_revision_mismatch")
                cur = con.execute(
                    "INSERT INTO sermon_collaboration_events(sermon_id, assignment_revision, actor_id, action, details_json, created_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (sermon_id, assignment_revision, actor_id.strip(), action, details, now),
                )
                event_id = int(cur.lastrowid)
                con.commit()
                return {
                    "id": event_id,
                    "sermon_id": sermon_id,
                    "assignment_revision": assignment_revision,
                    "actor_id": actor_id.strip(),
                    "action": action,
                    "details": json.loads(details),
                    "created_at": now,
                }
            except Exception:
                con.rollback()
                raise

    def list_workflow_events(
        self,
        sermon_id: int,
        *,
        assignment_revision: int | None = None,
        version: int | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["sermon_id=?", "action='review_status'"]
        params: list[Any] = [sermon_id]
        if assignment_revision is not None:
            clauses.append("assignment_revision=?")
            params.append(assignment_revision)
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT id, sermon_id, assignment_revision, actor_id, action, details_json, created_at "
                "FROM sermon_collaboration_events WHERE " + " AND ".join(clauses) + " ORDER BY id",
                params,
            ).fetchall()
        events = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            if version is not None and int(item["details"].get("version", 0)) != version:
                continue
            events.append(item)
        return events


__all__ = ["SermonCollaborationRepository"]
