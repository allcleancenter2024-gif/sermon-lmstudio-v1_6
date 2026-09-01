"""SQLite persistence for doctrine source chunks, independent of app.core."""

from __future__ import annotations

from contextlib import contextmanager
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


def _ensure_doctrine_table(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS doctrine_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tradition TEXT NOT NULL,
                title TEXT NOT NULL,
                section TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT '',
                license_note TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_doctrine_tradition ON doctrine_chunks(tradition);
            """
        )


def add_doctrine_chunk(data: dict, db_path: Path = DB_PATH) -> int:
    _ensure_doctrine_table(db_path)
    with _connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO doctrine_chunks(tradition, title, section, text, source_url, license_note)
               VALUES(?, ?, ?, ?, ?, ?)""",
            (str(data["tradition"]).strip(), str(data["title"]).strip(), str(data.get("section", "")).strip(),
             str(data["text"]).strip(), str(data.get("source_url", "")).strip(), str(data.get("license_note", "")).strip()),
        )
        return int(cur.lastrowid)


def fetch_doctrine_chunks(db_path: Path = DB_PATH) -> list[dict]:
    """Fetch doctrine chunks in the stable order used by index construction."""
    _ensure_doctrine_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            "SELECT id, tradition, title, section, text FROM doctrine_chunks ORDER BY id"
        )]


def _ensure_doctrine_embedding_table(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS doctrine_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                vector_blob BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                norm REAL NOT NULL,
                UNIQUE(chunk_id, model)
            );
            """
        )


def persist_doctrine_embeddings(rows, model: str, db_path: Path = DB_PATH) -> int:
    """Upsert one precomputed embedding batch in a single transaction."""
    _ensure_doctrine_embedding_table(db_path)
    written = 0
    with _connect(db_path) as con:
        for chunk_id, packed, dimension, norm in rows:
            con.execute(
                """INSERT INTO doctrine_embeddings(chunk_id, model, vector_blob, dimension, norm)
                   VALUES(?, ?, ?, ?, ?) ON CONFLICT(chunk_id, model) DO UPDATE SET
                   vector_blob=excluded.vector_blob, dimension=excluded.dimension, norm=excluded.norm""",
                (int(chunk_id), model, packed, int(dimension), float(norm)),
            )
            written += 1
    return written


def fetch_doctrine_vector_rows(model: str, tradition: str, db_path: Path = DB_PATH) -> list[dict]:
    """Fetch raw doctrine vectors and source fields for Core-side scoring."""
    _ensure_doctrine_table(db_path)
    _ensure_doctrine_embedding_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            """SELECT d.id, d.tradition, d.title, d.section, d.text, d.source_url, d.license_note, e.vector_blob, e.norm
               FROM doctrine_embeddings e JOIN doctrine_chunks d ON d.id=e.chunk_id
               WHERE e.model=? AND (d.tradition=? OR d.tradition='공통')""",
            (model, tradition),
        )]
