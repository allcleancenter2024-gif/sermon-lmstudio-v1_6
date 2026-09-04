"""Application boundary for scripture and original-language routes.

The legacy core functions remain the compatibility implementation.  Keeping
this boundary small lets the router depend on an application contract without
moving the SQLite schema or changing the public HTTP API.
"""

from app.core import (
    add_passage,
    bible_database_dashboard,
    bible_database_integrity,
    compare_reference,
    import_items,
    original_language_coverage,
)


def original_coverage(reference: str) -> dict:
    return original_language_coverage(reference)


def database_dashboard() -> dict:
    return bible_database_dashboard()


def database_integrity() -> dict:
    return bible_database_integrity()


def compare(reference: str) -> list[dict]:
    return compare_reference(reference)


def create_passage(*, translation: str, language: str, reference: str, text: str, license_note: str) -> None:
    add_passage(translation, language, reference, text, license_note)


def import_passages(items: list[dict]) -> int:
    return import_items(items)
