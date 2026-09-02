"""Read-only SBLGNT Greek text service."""

from pathlib import Path

from app.references import parse_reference
from app.repositories.greek_text import get_verses


def get_greek_text(reference: str, db_path: Path | None = None) -> dict:
    parsed = parse_reference(reference)
    if parsed.start_verse != parsed.end_verse:
        raise ValueError("헬라어 원문 조회 API는 한 절씩 조회해야 합니다.")
    rows = get_verses(parsed.book, parsed.chapter, parsed.start_verse, db_path) if db_path else get_verses(parsed.book, parsed.chapter, parsed.start_verse)
    return {
        "reference": f"{parsed.book} {parsed.chapter}:{parsed.start_verse}",
        "source_status": "available" if rows else "not_imported",
        "items": [{"text": row["text"], "source": {"name": row["source_name"], "version": row["source_version"], "file": row["source_file"], "sha256": row["source_sha256"]}, "validation_status": row["validation_status"]} for row in rows],
    }
