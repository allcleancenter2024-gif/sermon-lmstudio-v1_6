"""Read-only status summary for the installed original-language sources."""

from pathlib import Path

from app.morphgnt import MORPHGNT_ROOT
from app.repositories.bible import DB_PATH, _connect
from app.sblgnt import SBLGNT_BOOK_FILENAMES, SBLGNT_ROOT


def _count_table(table: str, db_path: Path) -> int:
    with _connect(db_path) as con:
        return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def original_language_dashboard(db_path: Path = DB_PATH, sblgnt_root: Path = SBLGNT_ROOT, morphgnt_root: Path = MORPHGNT_ROOT) -> dict:
    """Return source/file/database counts without changing files or schema."""
    sblgnt_books = sorted(Path(sblgnt_root).joinpath("books").glob("*.xml"))
    apparatus = sorted(Path(sblgnt_root).joinpath("apparatus").glob("*.xml"))
    morphgnt = sorted(Path(morphgnt_root).glob("*-morphgnt.txt"))
    expected = len(SBLGNT_BOOK_FILENAMES)
    return {
        "version": "v1.2",
        "sources": {
            "sblgnt": {"files": len(sblgnt_books), "expected": expected, "status": "ready" if len(sblgnt_books) == expected else "incomplete"},
            "apparatus": {"files": len(apparatus), "expected": expected, "status": "ready" if len(apparatus) == expected else "incomplete"},
            "morphgnt": {"files": len(morphgnt), "expected": expected, "status": "ready" if len(morphgnt) == expected else "incomplete"},
        },
        "database": {
            "sblgnt_verses": _count_table("greek_nt_verses", db_path),
            "morphgnt_tokens": _count_table("greek_nt_tokens", db_path),
            "original_notes": _count_table("original_word_notes", db_path),
            "pronunciation_tokens": _count_table("original_pronunciations", db_path),
            "apparatus_notes": _count_table("textual_variants", db_path),
        },
        "metadata": {
            "source_json": str(Path(sblgnt_root) / "metadata" / "source.json"),
            "attribution": str(Path(sblgnt_root) / "metadata" / "ATTRIBUTION.md"),
            "available": (Path(sblgnt_root) / "metadata" / "source.json").is_file() and (Path(sblgnt_root) / "metadata" / "ATTRIBUTION.md").is_file(),
        },
    }
