"""Optional SQLite FTS5 lexical strategy; legacy LIKE search remains default."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.paths import DATA_DIR
from app.repositories.bible import search_passages

DB_PATH = DATA_DIR / "bible.db"
FTS_TABLE = "rag_fts"


@contextmanager
def _connect(db_path: Path):
    con = sqlite3.connect(db_path)
    try:
        with con:
            yield con
    finally:
        con.close()


def lexical_strategy() -> str:
    value = os.getenv("RAG_LEXICAL_STRATEGY", "legacy").strip().lower()
    return value if value in {"legacy", "fts5"} else "legacy"


def fts5_supported(db_path: Path = DB_PATH) -> bool:
    try:
        with _connect(db_path) as con:
            con.execute("CREATE VIRTUAL TABLE temp.fts5_test USING fts5(content)")
            con.execute("DROP TABLE temp.fts5_test")
        return True
    except sqlite3.Error:
        return False


def ensure_fts_table(db_path: Path = DB_PATH) -> bool:
    if not fts5_supported(db_path):
        return False
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(source_id UNINDEXED, reference, text, source_name)"
        )
    return True


def rebuild_fts_index(db_path: Path = DB_PATH) -> int:
    """Rebuild the derived FTS index from existing passages without rewriting them."""
    if not ensure_fts_table(db_path):
        return 0
    with _connect(db_path) as con:
        rows = con.execute("SELECT id, reference, text, translation FROM passages ORDER BY id").fetchall()
        con.execute(f"DELETE FROM {FTS_TABLE}")
        con.executemany(
            f"INSERT INTO {FTS_TABLE}(source_id, reference, text, source_name) VALUES (?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def fts_search(query: str, limit: int = 24, db_path: Path = DB_PATH) -> list[dict]:
    """Search the derived FTS index, falling back to legacy LIKE on any failure."""
    try:
        if not ensure_fts_table(db_path):
            return search_passages(query, limit=limit, db_path=db_path)
        with _connect(db_path) as con:
            con.row_factory = sqlite3.Row
            # Keep exact reference lookup available alongside tokenized text search.
            direct = search_passages(query, limit=limit, db_path=db_path)
            tokens = [token for token in query.strip().split() if token]
            if not tokens:
                return direct
            match = " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens[:8])
            rows = con.execute(
                f"SELECT p.id, p.translation, p.language, p.reference, p.text, p.license_note, bm25({FTS_TABLE}) AS fts_score "
                f"FROM {FTS_TABLE} f JOIN passages p ON p.id=CAST(f.source_id AS INTEGER) WHERE {FTS_TABLE} MATCH ? "
                "ORDER BY fts_score LIMIT ?",
                (match, limit),
            ).fetchall()
            result = [dict(row) | {"retrieval_type": "fts5", "score": float(-row["fts_score"])} for row in rows]
            seen = {item["id"] for item in result}
            for item in direct:
                if item["id"] not in seen:
                    item = dict(item)
                    item["retrieval_type"] = "lexical"
                    result.append(item)
            return result[:limit]
    except (sqlite3.Error, ValueError, TypeError):
        return search_passages(query, limit=limit, db_path=db_path)
