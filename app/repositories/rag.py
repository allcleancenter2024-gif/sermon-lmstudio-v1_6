"""Read-only RAG statistics persistence, independent of app.core."""

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


def _ensure_rag_tables(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS rag_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passage_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                vector_blob BLOB,
                norm REAL,
                UNIQUE(passage_id, model)
            );
            CREATE INDEX IF NOT EXISTS idx_rag_model ON rag_embeddings(model);
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


def fetch_rag_stats(db_path: Path = DB_PATH) -> dict:
    """Fetch counts and model names for Bible and Doctrine embeddings."""
    _ensure_rag_tables(db_path)
    with _connect(db_path) as con:
        indexed = con.execute("SELECT COUNT(*) FROM rag_embeddings").fetchone()[0]
        models = [row[0] for row in con.execute("SELECT DISTINCT model FROM rag_embeddings ORDER BY model")]
        doctrine_indexed = con.execute("SELECT COUNT(*) FROM doctrine_embeddings").fetchone()[0]
        doctrine_models = [row[0] for row in con.execute("SELECT DISTINCT model FROM doctrine_embeddings ORDER BY model")]
    return {"indexed": indexed, "models": models, "doctrine_indexed": doctrine_indexed, "doctrine_models": doctrine_models}


def fetch_rag_vector_rows(model: str, db_path: Path = DB_PATH) -> list[dict]:
    """Fetch raw Bible passage vectors for Core-side scoring."""
    _ensure_rag_tables(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            """SELECT p.id, p.translation, p.language, p.reference, p.text, p.license_note,
                      e.vector_json, e.vector_blob, e.norm
               FROM rag_embeddings e JOIN passages p ON p.id=e.passage_id WHERE e.model=?""",
            (model,),
        )]


def fetch_rag_passages(db_path: Path = DB_PATH) -> list[dict]:
    """Fetch passages in the stable order expected by RAG indexing."""
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(
            "SELECT id, translation, language, reference, text FROM passages ORDER BY id"
        )]


def persist_rag_embeddings(rows, model: str, db_path: Path = DB_PATH) -> int:
    """Upsert one precomputed Bible embedding batch in a single transaction."""
    _ensure_rag_tables(db_path)
    written = 0
    with _connect(db_path) as con:
        for passage_id, packed, dimension, norm in rows:
            con.execute(
                """INSERT INTO rag_embeddings(passage_id, model, vector_json, dimension, vector_blob, norm)
                   VALUES(?, ?, ?, ?, ?, ?)
                   ON CONFLICT(passage_id, model) DO UPDATE SET
                   vector_json=excluded.vector_json, dimension=excluded.dimension,
                   vector_blob=excluded.vector_blob, norm=excluded.norm""",
                (int(passage_id), model, "[]", int(dimension), packed, float(norm)),
            )
            written += 1
    return written
