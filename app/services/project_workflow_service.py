"""Pure project workflow calculation.

The service owns the seven-step status calculation but knows nothing about
SQLite, FastAPI, or the legacy core module. Persistence and review/audit/lock
lookups are supplied by callers so the existing compatibility wrapper can
remain unchanged while the calculation becomes independently testable.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any


VersionLoader = Callable[[int, Path], list[dict[str, Any]]]
ReviewLoader = Callable[[int, int, Path], dict[str, Any]]


def build_workflow_status(
    sermon_id: int,
    version: int,
    db_path: Path,
    *,
    load_versions: VersionLoader,
    load_review_state: ReviewLoader,
) -> dict[str, Any]:
    """Calculate workflow state from immutable version and review records."""
    item = next((x for x in load_versions(sermon_id, db_path) if x["version"] == version), None)
    if not item:
        raise ValueError("설교 버전을 찾을 수 없습니다.")
    meta = item.get("metadata") or {}
    sources = meta.get("sources") if isinstance(meta.get("sources"), list) else []
    notes = meta.get("original_notes") if isinstance(meta.get("original_notes"), list) else []
    translations = {str(x.get("translation", "")).strip() for x in sources if isinstance(x, dict) and x.get("translation")}
    languages = {str(x.get("language", "")).strip() for x in sources if isinstance(x, dict) and x.get("language")}
    study_note = meta.get("study_note") if isinstance(meta.get("study_note"), dict) else {}
    study_counts = study_note.get("counts") if isinstance(study_note.get("counts"), dict) else {}
    study_language_ready = int(study_counts.get("translations") or 0) >= 2 or int(study_counts.get("original_notes") or 0) > 0
    review = load_review_state(sermon_id, version, db_path)
    audit = review.get("audit") or {}
    audit_status = audit.get("status")
    locked_ok = bool(review.get("locked") and (review.get("lock") or {}).get("integrity_ok"))
    reviewed = review.get("state") in {"approved", "locked"}

    def step(key: str, title: str, status: str, detail: str) -> dict[str, str]:
        return {"key": key, "title": title, "status": status, "detail": detail}

    steps = [
        step("brief", "1. 주제·본문 설정", "completed", str(meta.get("main_reference") or "저장된 설교 요청")),
        step("bible", "2. 성경 본문 연구", "completed" if sources else "attention",
             f"등록 근거 {len(sources)}건" if sources else "저장된 성경 근거가 없습니다."),
        step("languages", "3. 번역·원어 비교", "completed" if (len(translations) >= 2 or notes or len(languages) >= 2 or study_language_ready) else "attention",
             f"생성근거 번역/자료 {len(translations)}종 · 원어 노트 {len(notes)}건 · 연구노트 {'저장됨' if study_note else '없음'}"),
        step("draft", "4. 설교 초안", "completed", f"저장 버전 v{version}"),
        step("evidence", "5. 근거 검증", "completed" if audit_status == "ready_for_review" else ("attention" if audit else "pending"),
             f"Audit: {audit_status or '없음'}"),
        step("review", "6. 목회자 검토·승인", "completed" if reviewed else ("attention" if review.get("state") == "changes_requested" else "pending"),
             f"검토 상태: {review.get('state', 'unreviewed')}"),
        step("final", "7. 최종 잠금·출력", "completed" if locked_ok else "pending",
             "SHA-256 무결성 확인 완료" if locked_ok else "승인 후 최종 잠금이 필요합니다."),
    ]
    next_step = next((x["key"] for x in steps if x["status"] != "completed"), "done")
    return {
        "sermon_id": sermon_id,
        "version": version,
        "steps": steps,
        "completed": sum(1 for x in steps if x["status"] == "completed"),
        "next_step": next_step,
        "locked": locked_ok,
    }
