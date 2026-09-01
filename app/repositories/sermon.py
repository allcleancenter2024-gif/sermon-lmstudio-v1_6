"""SQLite persistence for sermon records and versions, independent of app.core."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import sqlite3
from pathlib import Path

from app.paths import DATA_DIR

DB_PATH = DATA_DIR / "bible.db"


@contextmanager
def _connect(*args, **kwargs):
    con = sqlite3.connect(*args, **kwargs)
    try:
        with con:
            yield con
    finally:
        con.close()


def _ensure_sermon_persistence_tables(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS sermons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sermon_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                UNIQUE(sermon_id, version)
            );
            CREATE TABLE IF NOT EXISTS generation_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sermon_id INTEGER,
                version INTEGER,
                status TEXT NOT NULL,
                model TEXT NOT NULL DEFAULT '',
                embedding_model TEXT NOT NULL DEFAULT '',
                search_mode TEXT NOT NULL DEFAULT '',
                source_count INTEGER NOT NULL DEFAULT 0,
                unchecked_json TEXT NOT NULL DEFAULT '[]',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                evidence_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            """
        )


def persist_sermon_version(
    topic: str, content: str, metadata: dict, sermon_id: int | None = None, db_path: Path = DB_PATH,
) -> dict:
    """Persist a sermon/version and link an eligible generation audit atomically."""
    _ensure_sermon_persistence_tables(db_path)
    now = datetime.now().isoformat(timespec="seconds")
    stored_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    with _connect(db_path) as con:
        if sermon_id is None:
            cur = con.execute("INSERT INTO sermons(topic, created_at) VALUES(?, ?)", (topic.strip() or "제목 없음", now))
            sermon_id = int(cur.lastrowid)
            version = 1
        else:
            exists = con.execute("SELECT 1 FROM sermons WHERE id=?", (sermon_id,)).fetchone()
            if not exists:
                raise ValueError("저장된 설교를 찾을 수 없습니다.")
            version = int(con.execute("SELECT COALESCE(MAX(version),0)+1 FROM sermon_versions WHERE sermon_id=?", (sermon_id,)).fetchone()[0])
        audit_id = stored_metadata.get("audit_id")
        audit_linked = False
        if audit_id:
            audit_row = con.execute("SELECT sermon_id, version FROM generation_audits WHERE id=?", (int(audit_id),)).fetchone()
            audit_linked = bool(audit_row and audit_row[0] is None and audit_row[1] is None)
            if not audit_linked:
                stored_metadata.pop("audit_id", None)
                stored_metadata.pop("audit", None)
                stored_metadata.pop("review_state", None)
        con.execute(
            "INSERT INTO sermon_versions(sermon_id, version, content, metadata_json, created_at) VALUES(?, ?, ?, ?, ?)",
            (sermon_id, version, content, json.dumps(stored_metadata, ensure_ascii=False), now),
        )
        if audit_linked:
            con.execute(
                "UPDATE generation_audits SET sermon_id=?, version=? WHERE id=? AND sermon_id IS NULL",
                (sermon_id, version, int(audit_id)),
            )
    return {"sermon_id": sermon_id, "version": version, "created_at": now, "audit_linked": audit_linked}
