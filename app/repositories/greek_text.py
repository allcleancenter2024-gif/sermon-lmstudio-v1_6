"""Read-only repository for normalized SBLGNT verse text."""

from pathlib import Path

from app.repositories.bible import DB_PATH, _connect
from app.sblgnt import ensure_greek_nt_verse_table


def get_verses(book_code: str, chapter: int, verse: int, db_path: Path = DB_PATH) -> list[dict]:
    ensure_greek_nt_verse_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = __import__("sqlite3").Row
        return [dict(row) for row in con.execute(
            "SELECT * FROM greek_nt_verses WHERE book_code=? AND chapter=? AND verse=? ORDER BY id",
            (book_code.upper(), int(chapter), int(verse)),
        )]
