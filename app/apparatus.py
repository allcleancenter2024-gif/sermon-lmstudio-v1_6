"""Read-only reader for the installed SBLGNT textual apparatus.

The apparatus is deliberately kept separate from the SBLGNT text and the
MorphGNT token table.  A note describes a textual variant; it is not an
alternative Bible text and must not silently replace the runtime passage.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from app.references import expand_reference, normalize_reference, parse_reference
from app.repositories.bible import DB_PATH, _connect
from app.sblgnt import SBLGNT_BOOK_FILENAMES, SBLGNT_ROOT


def _text(element: ET.Element) -> str:
    return " ".join(part.strip() for part in element.itertext() if part.strip())


def parse_apparatus_content(content: str, source_file: str = "", source_sha256: str = "") -> list[dict]:
    """Parse one SBLGNT apparatus XML document into independent notes."""
    if re.search(r"<!\s*(?:doctype|entity)\b", content, flags=re.IGNORECASE):
        raise ValueError("외부 DTD/ENTITY가 포함된 Apparatus XML은 보안상 읽을 수 없습니다.")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ValueError(f"Apparatus XML 형식이 올바르지 않습니다: {exc}") from exc

    current_reference = ""
    items: list[dict] = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower() if isinstance(element.tag, str) else ""
        if tag == "verse":
            raw_reference = _text(element)
            try:
                current_reference = normalize_reference(raw_reference)
            except ValueError:
                current_reference = raw_reference
        elif tag == "note" and current_reference:
            note = _text(element)
            if not note:
                continue
            items.append({
                "reference": current_reference,
                "note": note,
                "source": {
                    "name": "SBLGNT Apparatus",
                    "version": "v1.2",
                    "file": source_file,
                    "sha256": source_sha256,
                },
                "validation_status": "source_note_only",
            })
    return items


def load_apparatus(reference: str, root: Path = SBLGNT_ROOT) -> dict:
    """Load notes for an exact same-chapter reference range from a book file."""
    wanted = expand_reference(reference)
    parsed = parse_reference(reference)
    filename = SBLGNT_BOOK_FILENAMES.get(parsed.book)
    source = Path(root) / "apparatus" / filename if filename else None
    if source is None or not source.is_file():
        return {
            "reference": normalize_reference(reference),
            "source_status": "not_installed",
            "source": None,
            "items": [],
        }

    raw = source.read_text(encoding="utf-8-sig")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    parsed_items = parse_apparatus_content(raw, str(source), digest)
    selected = [item for item in parsed_items if item["reference"] in wanted]
    return {
        "reference": normalize_reference(reference),
        "source_status": "available" if selected else "no_variants_recorded",
        "source": {"file": str(source), "sha256": digest, "version": "v1.2"},
        "items": selected,
    }


def ensure_textual_variants_table(db_path: Path = DB_PATH) -> None:
    """Create the isolated apparatus table without changing existing schemas."""
    with _connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS textual_variants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL, source_version TEXT NOT NULL, source_file TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, book_code TEXT NOT NULL, chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL, canonical_reference TEXT NOT NULL, note_index INTEGER NOT NULL,
            token_position INTEGER, reading TEXT, witness TEXT, category TEXT, note TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}', import_batch_id TEXT NOT NULL,
            validation_status TEXT NOT NULL DEFAULT 'source_note_only', created_at TEXT NOT NULL,
            UNIQUE(source_name, source_version, book_code, chapter, verse, note_index)
        )""")
        con.executescript("""CREATE INDEX IF NOT EXISTS idx_textual_variants_reference
            ON textual_variants(book_code, chapter, verse);
        CREATE INDEX IF NOT EXISTS idx_textual_variants_source
            ON textual_variants(source_name, source_version);""")


def import_apparatus_directory(root: Path = SBLGNT_ROOT / "apparatus", db_path: Path = DB_PATH, persist: bool = True) -> dict:
    """Validate and idempotently import all book-level apparatus XML files."""
    root = Path(root)
    expected = set(SBLGNT_BOOK_FILENAMES.values())
    files = sorted(root.glob("*.xml"))
    if {path.name for path in files} != expected:
        raise ValueError(f"SBLGNT Apparatus 27개 책 파일이 필요합니다. 현재 {len(files)}개가 감지되었습니다.")

    all_items: list[dict] = []
    reports: list[dict] = []
    for path in files:
        raw = path.read_bytes()
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path.name}: UTF-8 decode 실패") from exc
        digest = hashlib.sha256(raw).hexdigest()
        parsed = parse_apparatus_content(content, path.name, digest)
        reports.append({"file": path.name, "notes": len(parsed), "sha256": digest})
        all_items.extend(parsed)

    batch_id = str(uuid.uuid4())
    if not persist:
        return {"files": len(files), "notes": len(all_items), "reports": reports, "batch_id": None, "database_changes": 0}

    ensure_textual_variants_table(db_path)
    reverse_books = {filename: code for code, filename in SBLGNT_BOOK_FILENAMES.items()}
    now = datetime.now(timezone.utc).isoformat()
    values = []
    counters: dict[tuple[str, int, int], int] = {}
    for item in all_items:
        parsed = parse_reference(item["reference"])
        key = (parsed.book, parsed.chapter, parsed.start_verse)
        counters[key] = counters.get(key, 0) + 1
        source_file = Path(item["source"]["file"]).name
        if reverse_books.get(source_file) != parsed.book:
            raise ValueError(f"{source_file}: Apparatus note reference와 책 파일이 일치하지 않습니다: {item['reference']}")
        values.append((
            item["source"]["name"], item["source"]["version"], source_file, item["source"]["sha256"],
            parsed.book, parsed.chapter, parsed.start_verse, item["reference"], counters[key],
            None, None, None, "apparatus_note", item["note"], json.dumps({"raw_note": item["note"]}, ensure_ascii=False),
            batch_id, item["validation_status"], now,
        ))
    with _connect(db_path) as con:
        con.executemany("""INSERT INTO textual_variants
            (source_name,source_version,source_file,source_sha256,book_code,chapter,verse,canonical_reference,
             note_index,token_position,reading,witness,category,note,metadata_json,import_batch_id,validation_status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_name,source_version,book_code,chapter,verse,note_index) DO UPDATE SET
              source_file=excluded.source_file, source_sha256=excluded.source_sha256, note=excluded.note,
              metadata_json=excluded.metadata_json, import_batch_id=excluded.import_batch_id,
              validation_status=excluded.validation_status""", values)
    return {"files": len(files), "notes": len(all_items), "reports": reports, "batch_id": batch_id, "database_changes": len(values)}
