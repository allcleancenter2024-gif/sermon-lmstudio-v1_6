"""Application boundary for denomination doctrine workflows.

Approval and licensing rules remain in their existing services; this facade
keeps HTTP routing separate from SQLite persistence and doctrine RAG details.
"""

from datetime import datetime, timezone
import sqlite3

from app.core import (
    DB_PATH, LMStudioClient, add_doctrine_chunk, rag_stats, recommend_related,
    register_translation_license, translation_licenses,
)
from app.doctrine_rag import build_approved_doctrine_index, search_approved_doctrine
from app.doctrine_workflow import fetch_indexable_doctrine_chunks, transition_document


def create_chunk(payload: dict) -> int:
    return add_doctrine_chunk(payload)


def indexable_chunks(db_path=DB_PATH) -> list[dict]:
    return fetch_indexable_doctrine_chunks(db_path)


def review_license(source_id: int, *, license_status: str, reviewer: str, permission_ref: str, note: str, db_path=DB_PATH) -> dict:
    active = 1 if license_status == "VERIFIED" else 0
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as con:
        row = con.execute("SELECT id FROM doctrine_sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise LookupError("교단 자료원을 찾지 못했습니다.")
        con.execute(
            "UPDATE doctrine_sources SET license_status=?, active=?, permission_ref=?, "
            "license_reviewed_by=?, license_reviewed_at=?, license_review_note=?, updated_at=? WHERE id=?",
            (license_status, active, permission_ref.strip(), reviewer, reviewed_at, note.strip(), reviewed_at, source_id),
        )
    return {"ok": True, "source_id": source_id, "license_status": license_status,
            "active": bool(active), "reviewed_by": reviewer, "reviewed_at": reviewed_at}


def review_document(document_id: int, *, actor: str, comment: str, db_path=DB_PATH) -> dict:
    return transition_document(document_id, "APPROVED", actor, comment, db_path)


def reindex(model: str, db_path=DB_PATH) -> dict:
    return build_approved_doctrine_index(LMStudioClient(), model, db_path)


def search(query: str, model: str, denomination_code: str, limit: int, include_common: bool, db_path=DB_PATH) -> list[dict]:
    return search_approved_doctrine(query, LMStudioClient(), model, denomination_code, db_path, limit, include_common)


def create_license(payload: dict) -> None:
    register_translation_license(payload)


def list_licenses() -> list[dict]:
    return translation_licenses()


def recommend(reference: str, model: str, limit: int) -> list[dict]:
    return recommend_related(reference, LMStudioClient(), model, min(max(limit, 1), 20))


def available_models() -> list[str]:
    return rag_stats()["models"]
