"""Read-only repository for the isolated SBLGNT textual apparatus table."""

from pathlib import Path

from app.apparatus import ensure_textual_variants_table
from app.repositories.bible import DB_PATH, _connect


def get_variants(book_code: str, chapter: int, verse: int, db_path: Path = DB_PATH) -> list[dict]:
    ensure_textual_variants_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = __import__("sqlite3").Row
        return [dict(row) for row in con.execute(
            "SELECT * FROM textual_variants WHERE book_code=? AND chapter=? AND verse=? ORDER BY note_index",
            (book_code.upper(), int(chapter), int(verse)),
        )]


def has_imported_variants(db_path: Path = DB_PATH) -> bool:
    ensure_textual_variants_table(db_path)
    with _connect(db_path) as con:
        return con.execute("SELECT 1 FROM textual_variants LIMIT 1").fetchone() is not None
