"""Server-side approval boundary for denomination doctrine documents."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

ALLOWED_TRANSITIONS = {
    "DISCOVERED": {"DOWNLOADED", "FAILED", "REJECTED"},
    "DOWNLOADED": {"PARSED", "FAILED", "REJECTED"},
    "PARSED": {"NEEDS_REVIEW", "FAILED", "REJECTED"},
    "NEEDS_REVIEW": {"APPROVED", "REJECTED", "FAILED"},
    "APPROVED": {"INDEXED", "SUPERSEDED", "DISABLED"},
    "INDEXED": {"SUPERSEDED", "DISABLED"},
    "REJECTED": {"NEEDS_REVIEW", "DISABLED"},
    "FAILED": {"DISCOVERED", "DISABLED"},
    "SUPERSEDED": {"DISABLED"},
    "DISABLED": set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def transition_document(document_id: int, to_status: str, actor: str, comment: str = "", db_path: Path = Path("data/bible.db")) -> dict:
    to_status = str(to_status).strip().upper()
    actor = str(actor).strip()
    if not actor:
        raise ValueError("문서 상태 변경에는 검토자 계정이 필요합니다.")
    with closing(sqlite3.connect(db_path)) as con, con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM doctrine_documents WHERE id=?", (int(document_id),)).fetchone()
        if not row:
            raise ValueError("교리 문서를 찾지 못했습니다.")
        current = str(row["review_status"])
        if to_status not in ALLOWED_TRANSITIONS.get(current, set()):
            raise ValueError(f"허용되지 않은 문서 상태 전이입니다: {current} → {to_status}")
        if to_status == "APPROVED":
            chunk_count = con.execute("SELECT COUNT(*) FROM doctrine_chunks_v2 WHERE document_id=?", (int(document_id),)).fetchone()[0]
            if not chunk_count:
                raise ValueError("청크가 없는 문서는 승인할 수 없습니다.")
            source = con.execute("SELECT license_status,active FROM doctrine_sources WHERE id=?", (int(row["source_id"]),)).fetchone()
            if not source or not source["active"] or source["license_status"] in {"UNKNOWN", "PERMISSION_REQUIRED", "RESTRICTED", "BLOCKED"}:
                raise ValueError("활성 자료원이 아니거나 라이선스 확인 전인 문서는 승인할 수 없습니다.")
        active = 1 if to_status in {"APPROVED", "INDEXED"} else 0
        con.execute("UPDATE doctrine_documents SET review_status=?, active=?, reviewed_by=?, reviewed_at=?, review_comment=? WHERE id=?", (to_status, active, actor, _now(), comment[:2000], int(document_id)))
        con.execute("INSERT INTO doctrine_audit_log(document_id,actor,action,from_status,to_status,comment,created_at) VALUES(?,?,?,?,?,?,?)", (int(document_id), actor, "status_change", current, to_status, comment[:2000], _now()))
    return {"document_id": int(document_id), "from_status": current, "review_status": to_status, "active": bool(active), "reviewed_by": actor}


def fetch_indexable_doctrine_chunks(db_path: Path) -> list[dict]:
    with closing(sqlite3.connect(db_path)) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute("""SELECT c.* FROM doctrine_chunks_v2 c JOIN doctrine_documents d ON d.id=c.document_id JOIN doctrine_sources s ON s.id=d.source_id JOIN denominations n ON n.id=s.denomination_id WHERE d.review_status IN ('APPROVED','INDEXED') AND d.active=1 AND s.active=1 AND n.active=1 AND s.license_status NOT IN ('UNKNOWN','PERMISSION_REQUIRED','BLOCKED') ORDER BY c.document_id,c.chunk_index""")]
