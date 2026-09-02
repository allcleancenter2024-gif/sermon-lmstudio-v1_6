"""Safe local catalog and book-first reader for SBLGNT source files.

The SQLite passages table remains the authoritative runtime/RAG store. This
module resolves local source files for import and validation only; it never
downloads or silently promotes XML into the database.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import uuid
from datetime import datetime, timezone

from app.importers import convert_bible_source
from app.paths import DATA_DIR
from app.references import expand_reference, parse_reference
from app.repositories.bible import DB_PATH, _connect


SBLGNT_ROOT = DATA_DIR / "bible" / "greek" / "sblgnt"
SBLGNT_SUBDIRS = ("full", "books", "apparatus")
SBLGNT_BOOK_FILENAMES = {
    "MAT": "Matt.xml", "MRK": "Mark.xml", "LUK": "Luke.xml", "JHN": "John.xml",
    "ACT": "Acts.xml", "ROM": "Rom.xml", "1CO": "1Cor.xml", "2CO": "2Cor.xml",
    "GAL": "Gal.xml", "EPH": "Eph.xml", "PHP": "Phil.xml", "COL": "Col.xml",
    "1TH": "1Thess.xml", "2TH": "2Thess.xml", "1TI": "1Tim.xml", "2TI": "2Tim.xml",
    "TIT": "Titus.xml", "PHM": "Phlm.xml", "HEB": "Heb.xml", "JAS": "Jas.xml",
    "1PE": "1Pet.xml", "2PE": "2Pet.xml", "1JN": "1John.xml", "2JN": "2John.xml",
    "3JN": "3John.xml", "JUD": "Jude.xml", "REV": "Rev.xml",
}


def ensure_sblgnt_layout(root: Path = SBLGNT_ROOT) -> Path:
    """Create the documented local source directories and return the root."""
    root = Path(root)
    for name in SBLGNT_SUBDIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def resolve_sblgnt_source(reference: str, root: Path = SBLGNT_ROOT) -> Path | None:
    """Return a book XML when present, otherwise the full XML when present."""
    book = parse_reference(reference).book
    root = Path(root)
    book_path = root / "books" / SBLGNT_BOOK_FILENAMES.get(book, "")
    if book_path.is_file():
        return book_path
    full_path = root / "full" / "sblgnt.xml"
    return full_path if full_path.is_file() else None


def load_sblgnt_passages(reference: str, root: Path = SBLGNT_ROOT) -> dict:
    """Read the requested book first and return normalized requested verses."""
    wanted = expand_reference(reference)
    source = resolve_sblgnt_source(reference, root)
    if source is None:
        return {"source": None, "source_kind": "missing", "items": [], "missing": wanted}
    _, items = convert_bible_source(source.read_text(encoding="utf-8-sig"), "sblgnt_xml")
    by_reference = {item["reference"]: item for item in items}
    selected = [by_reference[key] for key in wanted if key in by_reference]
    return {
        "source": str(source),
        "source_kind": "book" if source.parent.name == "books" else "full",
        "items": selected,
        "missing": [key for key in wanted if key not in by_reference],
    }


def ensure_greek_nt_verse_table(db_path: Path = DB_PATH) -> None:
    with _connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS greek_nt_verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL, source_version TEXT NOT NULL,
            source_file TEXT NOT NULL, source_sha256 TEXT NOT NULL, book_code TEXT NOT NULL,
            chapter INTEGER NOT NULL, verse INTEGER NOT NULL, canonical_reference TEXT NOT NULL,
            text TEXT NOT NULL, import_batch_id TEXT NOT NULL, validation_status TEXT NOT NULL DEFAULT 'validated',
            created_at TEXT NOT NULL, UNIQUE(source_name, source_version, book_code, chapter, verse)
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_greek_nt_verses_reference ON greek_nt_verses(book_code, chapter, verse)")


def import_sblgnt_books(root: Path = SBLGNT_ROOT, db_path: Path = DB_PATH, persist: bool = True) -> dict:
    """Import book-level SBLGNT verses; raw XML remains the immutable source."""
    root = Path(root)
    reports, passages = [], []
    for book_code, filename in SBLGNT_BOOK_FILENAMES.items():
        path = root / "books" / filename
        if not path.is_file():
            raise ValueError(f"SBLGNT 책별 XML이 없습니다: {filename}")
        raw = path.read_bytes()
        content = raw.decode("utf-8-sig")
        _, items = convert_bible_source(content, "sblgnt_xml")
        reports.append({"file": filename, "verses": len(items), "sha256": hashlib.sha256(raw).hexdigest()})
        for item in items:
            parsed = parse_reference(item["reference"])
            if parsed.book != book_code:
                raise ValueError(f"{filename}: reference 책 코드 불일치: {item['reference']}")
            passages.append((book_code, filename, hashlib.sha256(raw).hexdigest(), parsed.chapter, parsed.start_verse, item["reference"], item["text"]))
    batch_id = str(uuid.uuid4())
    if not persist:
        return {"files": len(reports), "verses": len(passages), "reports": reports, "batch_id": None, "database_changes": 0}
    ensure_greek_nt_verse_table(db_path)
    now = datetime.now(timezone.utc).isoformat()
    values = [("SBLGNT", "v1.2", filename, sha256, book, chapter, verse, reference, text, batch_id, "validated", now) for book, filename, sha256, chapter, verse, reference, text in passages]
    with _connect(db_path) as con:
        con.executemany("""INSERT INTO greek_nt_verses
            (source_name,source_version,source_file,source_sha256,book_code,chapter,verse,canonical_reference,text,import_batch_id,validation_status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_name,source_version,book_code,chapter,verse) DO UPDATE SET
              source_file=excluded.source_file, source_sha256=excluded.source_sha256, text=excluded.text,
              import_batch_id=excluded.import_batch_id, validation_status=excluded.validation_status""", values)
    return {"files": len(reports), "verses": len(passages), "reports": reports, "batch_id": batch_id, "database_changes": len(values)}
