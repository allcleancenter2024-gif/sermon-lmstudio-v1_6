"""Application service for read-only textual apparatus lookups."""

from pathlib import Path

from app.apparatus import load_apparatus
from app.references import parse_reference
from app.repositories.textual_apparatus import get_variants, has_imported_variants


def get_apparatus_notes(reference: str, db_path: Path | None = None, root: Path | None = None) -> dict:
    """Read normalized apparatus rows at runtime; XML is only the ingestion source."""
    if root is not None:
        return load_apparatus(reference, root)
    parsed = parse_reference(reference)
    rows = get_variants(parsed.book, parsed.chapter, parsed.start_verse, db_path) if db_path else get_variants(parsed.book, parsed.chapter, parsed.start_verse)
    items = [{
        "reference": row["canonical_reference"], "note": row["note"],
        "source": {"name": row["source_name"], "version": row["source_version"], "file": row["source_file"], "sha256": row["source_sha256"]},
        "validation_status": row["validation_status"],
    } for row in rows]
    status = "available" if items else "no_variants_recorded" if (has_imported_variants(db_path) if db_path else has_imported_variants()) else "not_imported"
    return {
        "reference": f"{parsed.book} {parsed.chapter}:{parsed.start_verse}",
        "source_status": status,
        "source": {"file": items[0]["source"]["file"], "sha256": items[0]["source"]["sha256"], "version": items[0]["source"]["version"]} if items else None,
        "items": items,
    }
