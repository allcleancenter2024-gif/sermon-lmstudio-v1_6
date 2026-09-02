"""Read-only repository for normalized MorphGNT tokens."""

from __future__ import annotations

from pathlib import Path

from app.morphgnt import ensure_greek_nt_token_table
from app.repositories.bible import DB_PATH, _connect


def get_tokens(book_code: str, chapter: int, verse: int, db_path: Path = DB_PATH) -> list[dict]:
    ensure_greek_nt_token_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = __import__("sqlite3").Row
        return [dict(row) for row in con.execute(
            "SELECT * FROM greek_nt_tokens WHERE book_code=? AND chapter=? AND verse=? ORDER BY token_index",
            (book_code.upper(), int(chapter), int(verse)),
        )]


def search_by_lemma(lemma: str, limit: int = 50, db_path: Path = DB_PATH) -> list[dict]:
    ensure_greek_nt_token_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = __import__("sqlite3").Row
        return [dict(row) for row in con.execute(
            "SELECT * FROM greek_nt_tokens WHERE lemma=? ORDER BY book_order, chapter, verse, token_index LIMIT ?",
            (lemma, max(1, min(int(limit), 500))),
        )]


def search_by_normalized_form(word: str, limit: int = 50, db_path: Path = DB_PATH) -> list[dict]:
    ensure_greek_nt_token_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = __import__("sqlite3").Row
        return [dict(row) for row in con.execute(
            "SELECT * FROM greek_nt_tokens WHERE normalized_form=? ORDER BY book_order, chapter, verse, token_index LIMIT ?",
            (word, max(1, min(int(limit), 500))),
        )]
