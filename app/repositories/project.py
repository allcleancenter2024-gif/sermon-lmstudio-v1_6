"""SQLite persistence for project metadata, independent of app.core."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from difflib import unified_diff
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


def _ensure_project_tables(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS sermons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sermon_project_meta (
                sermon_id INTEGER PRIMARY KEY,
                service_date TEXT NOT NULL DEFAULT '',
                series_name TEXT NOT NULL DEFAULT '',
                preacher TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            """
        )


def get_project_meta(sermon_id: int, db_path: Path = DB_PATH) -> dict:
    _ensure_project_tables(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT sermon_id, service_date, series_name, preacher, notes, updated_at "
            "FROM sermon_project_meta WHERE sermon_id=?",
            (sermon_id,),
        ).fetchone()
    return dict(row) if row else {
        "sermon_id": sermon_id, "service_date": "", "series_name": "", "preacher": "", "notes": "", "updated_at": "",
    }


def update_project_meta(
    sermon_id: int, *, service_date: str = "", series_name: str = "", preacher: str = "", notes: str = "",
    db_path: Path = DB_PATH,
) -> dict:
    _ensure_project_tables(db_path)
    with _connect(db_path) as con:
        if not con.execute("SELECT 1 FROM sermons WHERE id=?", (sermon_id,)).fetchone():
            raise ValueError("프로젝트 정보를 저장할 설교를 찾을 수 없습니다.")
        now = datetime.now().isoformat(timespec="seconds")
        con.execute(
            """INSERT INTO sermon_project_meta(sermon_id, service_date, series_name, preacher, notes, updated_at)
               VALUES(?, ?, ?, ?, ?, ?)
               ON CONFLICT(sermon_id) DO UPDATE SET service_date=excluded.service_date, series_name=excluded.series_name,
               preacher=excluded.preacher, notes=excluded.notes, updated_at=excluded.updated_at""",
            (sermon_id, service_date.strip(), series_name.strip(), preacher.strip(), notes.strip(), now),
        )
    return get_project_meta(sermon_id, db_path)


def _ensure_sermon_list_tables(db_path: Path) -> None:
    """Create the existing sermon tables needed by the list-only query."""
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
            """
        )


def list_sermons(db_path: Path = DB_PATH) -> list[dict]:
    """List sermons with their latest stored version number."""
    _ensure_sermon_list_tables(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            """SELECT s.id, s.topic, s.created_at, MAX(v.version) AS latest_version
               FROM sermons s JOIN sermon_versions v ON v.sermon_id=s.id GROUP BY s.id ORDER BY s.id DESC"""
        )]


def sermon_versions(sermon_id: int, db_path: Path = DB_PATH) -> list[dict]:
    """Return stored versions for one sermon, newest first."""
    _ensure_sermon_list_tables(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT version, content, metadata_json, created_at FROM sermon_versions WHERE sermon_id=? ORDER BY version DESC",
            (sermon_id,),
        )
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            result.append(item)
        return result


def compare_sermon_versions(sermon_id: int, a: int, b: int, db_path: Path = DB_PATH) -> str:
    """Return a unified diff between two stored sermon versions."""
    versions = {item["version"]: item["content"] for item in sermon_versions(sermon_id, db_path)}
    if a not in versions or b not in versions:
        raise ValueError("비교할 버전을 찾을 수 없습니다.")
    return "\n".join(unified_diff(versions[a].splitlines(), versions[b].splitlines(), fromfile=f"v{a}", tofile=f"v{b}", lineterm=""))


def fetch_project_dashboard_inputs(db_path: Path = DB_PATH) -> list[dict]:
    """Fetch dashboard base rows; workflow state remains a core responsibility."""
    inputs = []
    for sermon in list_sermons(db_path):
        sermon_id = int(sermon["id"])
        version = int(sermon["latest_version"])
        version_item = next((item for item in sermon_versions(sermon_id, db_path) if item["version"] == version), None)
        if not version_item:
            continue
        inputs.append({
            "sermon": sermon,
            "version": version,
            "version_item": version_item,
            "project": get_project_meta(sermon_id, db_path),
        })
    return inputs


def _legacy_ensure_sermon_persistence_tables(db_path: Path) -> None:
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


def _legacy_persist_sermon_version(
    topic: str, content: str, metadata: dict, sermon_id: int | None = None, db_path: Path = DB_PATH,
) -> dict:
    """Persist a sermon/version and link an eligible generation audit atomically."""
    _legacy_ensure_sermon_persistence_tables(db_path)
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


# Compatibility re-export; implementation lives in the Sermon repository.
from app.repositories.sermon import persist_sermon_version
