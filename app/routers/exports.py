from __future__ import annotations
from datetime import datetime
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from app.paths import EXPORTS_DIR
from app.paths import USER_ROOT
from app.auth import session_user, user_exists
from app.repositories.collaboration import SermonCollaborationRepository
from app.application.exports_facade import (
    DB_PATH, build_grounding_report_data, dashboard_html, estimate_minutes,
    get_generation_audit, get_project_meta, get_reading_cpm, list_sermons,
    page_format_v2_enabled, record_event, render, render_grounding_html,
    render_grounding_markdown, render_to_path, safe_report_stem, save_sermon,
    select_output, sermon_document, sermon_review_state, sermon_versions,
    v2_is_selected, with_legacy_fallback, write_docx, write_final_package, write_pdf,
)

router=APIRouter(); EXPORTS=EXPORTS_DIR
_collaboration_repository = SermonCollaborationRepository(DB_PATH)
_auth_db = USER_ROOT / "auth.sqlite3"

def _enforce_assigned_version_export(data: dict, request: Request) -> None:
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    sermon_id, version = meta.get("sermon_id"), meta.get("version")
    if sermon_id is None:
        return
    try:
        assignment = _collaboration_repository.get_assignment(int(sermon_id))
    except RuntimeError as exc:
        if "migration is required" in str(exc):
            return
        raise
    if assignment is None:
        raise HTTPException(409, {"code": "collaboration_assignment_required", "detail": "협업 담당자를 먼저 배정해야 합니다."})
    actor = session_user(request.cookies.get("sermon_session"))
    if not actor or not user_exists(_auth_db, actor):
        raise HTTPException(401, {"code": "auth_required", "detail": "최종 설교 출력에는 로그인이 필요합니다."})
    if actor != assignment["approver_id"]:
        raise HTTPException(403, {"code": "approver_required", "detail": "배정된 승인자만 최종 설교를 출력할 수 있습니다."})
    try:
        version = int(version)
    except (TypeError, ValueError):
        raise HTTPException(409, {"code": "version_required", "detail": "저장된 설교 버전을 확인할 수 없습니다."})
    versions = sermon_versions(int(sermon_id))
    if not versions or version != max(int(item["version"]) for item in versions):
        raise HTTPException(409, {"code": "latest_version_required", "detail": "최신 승인 버전만 출력할 수 있습니다."})
    version_item = next((item for item in versions if int(item["version"]) == version), None)
    if not version_item or str(data.get("text") or "") != str(version_item.get("content") or ""):
        raise HTTPException(409, {"code": "saved_version_content_required", "detail": "저장된 승인 버전 원문과 일치하는 문서만 출력할 수 있습니다."})
    state = sermon_review_state(int(sermon_id), version)
    lock = state.get("lock") or {}
    history = state.get("history") or []
    all_events = _collaboration_repository.list_workflow_events(int(sermon_id), version=version)
    active_events = [item for item in all_events if int(item["assignment_revision"]) == int(assignment["revision"])]
    if history and not active_events:
        raise HTTPException(409, {"code": "new_version_required", "detail": "담당자가 바뀐 설교는 새 버전에서 다시 검토·승인해야 합니다."})
    has_review = any(item["actor_id"] == assignment["reviewer_id"] and item["details"].get("status") == "reviewed" for item in active_events)
    has_approval = any(item["actor_id"] == assignment["approver_id"] and item["details"].get("status") == "approved" for item in active_events)
    if not state.get("locked") or not lock.get("integrity_ok") or lock.get("locked_by") != assignment["approver_id"] or not has_review or not has_approval:
        raise HTTPException(409, {"code": "approval_chain_incomplete", "detail": "검토·승인·무결성 잠금이 확인된 최신 버전만 출력할 수 있습니다."})

def _page_document(data:dict):
    meta=data.get("meta") if isinstance(data.get("meta"),dict) else {}
    sources=data.get("sources") if isinstance(data.get("sources"),list) else []
    return sermon_document(sermon=str(data.get("text", "")), meta=meta, sources=sources)
def _page_selection(data:dict, default_format:str):
    return select_output(document_type="sermon", format=default_format, profile=data.get("profile"), theme=data.get("theme"), preset=data.get("preset"))
def _use_v2(data:dict) -> bool:
    selected = page_format_v2_enabled() or v2_is_selected(str(data.get("render_id") or uuid.uuid4().hex))
    record_event("v2_used" if selected else "legacy_used", format="export", profile=data.get("profile") or "sermon", theme=data.get("theme"), preset=data.get("preset"))
    return selected
@router.post("/api/export/markdown")
def export_markdown(data:dict, request: Request):
    _enforce_assigned_version_export(data, request)
    text=str(data.get("text","")).strip()
    if not text: raise HTTPException(400,"내보낼 설교문이 없습니다.")
    path=EXPORTS/f"sermon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"; selection=_page_selection(data, "markdown"); content=with_legacy_fallback(format="markdown",profile=selection["profile"],theme=selection["theme"],preset=selection["preset"],render_v2=lambda: render(_page_document(data), selection["format"], selection["profile"], {"theme": selection["theme"]}),render_legacy=lambda: text) if _use_v2(data) else text; path.write_text(content,encoding="utf-8"); return {"filename":path.name,"url":f"/downloads/{path.name}"}
@router.post("/api/export/html")
def export_html(data:dict, request: Request):
    _enforce_assigned_version_export(data, request)
    text=str(data.get("text","")).strip()
    if not text: raise HTTPException(400,"내보낼 설교문이 없습니다.")
    path=EXPORTS/f"sermon_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"; selection=_page_selection(data, "html"); legacy=lambda: dashboard_html(sermon=text,meta=data.get("meta") if isinstance(data.get("meta"),dict) else {},sources=data.get("sources") if isinstance(data.get("sources"),list) else []); content=with_legacy_fallback(format="html",profile=selection["profile"],theme=selection["theme"],preset=selection["preset"],render_v2=lambda: render(_page_document(data), selection["format"], selection["profile"], {"theme": selection["theme"]}),render_legacy=legacy) if _use_v2(data) else legacy(); path.write_text(content,encoding="utf-8"); return {"filename":path.name,"url":f"/downloads/{path.name}"}
@router.post("/api/export/word")
def export_word(data:dict, request: Request):
    _enforce_assigned_version_export(data, request)
    text=str(data.get("text","")).strip()
    if not text: raise HTTPException(400,"내보낼 설교문이 없습니다.")
    path=EXPORTS/f"sermon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    try:
        selection = _page_selection(data, "docx")
        if _use_v2(data):
            with_legacy_fallback(format="docx",profile=selection["profile"],theme=selection["theme"],preset=selection["preset"],render_v2=lambda: render_to_path(_page_document(data), selection["format"], path, selection["profile"], {"theme": selection["theme"], "preset": selection["preset"]}),render_legacy=lambda: write_docx(path,sermon=text,meta=data.get("meta") if isinstance(data.get("meta"),dict) else {}))
        else: write_docx(path,sermon=text,meta=data.get("meta") if isinstance(data.get("meta"),dict) else {})
    except RuntimeError as exc: raise HTTPException(503,str(exc)) from exc
    return {"filename":path.name,"url":f"/downloads/{path.name}"}
@router.post("/api/export/pdf")
def export_pdf(data:dict, request: Request):
    _enforce_assigned_version_export(data, request)
    text=str(data.get("text","")).strip()
    if not text: raise HTTPException(400,"내보낼 설교문이 없습니다.")
    path=EXPORTS/f"sermon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    try:
        selection = _page_selection(data, "pdf")
        if _use_v2(data):
            with_legacy_fallback(format="pdf",profile=selection["profile"],theme=selection["theme"],preset=selection["preset"],render_v2=lambda: render_to_path(_page_document(data), selection["format"], path, selection["profile"], {"theme": selection["theme"], "preset": selection["preset"]}),render_legacy=lambda: write_pdf(path,sermon=text,meta=data.get("meta") if isinstance(data.get("meta"),dict) else {},sources=data.get("sources") if isinstance(data.get("sources"),list) else []))
        else: write_pdf(path,sermon=text,meta=data.get("meta") if isinstance(data.get("meta"),dict) else {},sources=data.get("sources") if isinstance(data.get("sources"),list) else [])
    except RuntimeError as exc: raise HTTPException(503,str(exc)) from exc
    return {"filename":path.name,"url":f"/downloads/{path.name}"}
@router.post("/api/export/grounding")
def export_grounding(data:dict, request: Request):
    _enforce_assigned_version_export(data, request)
    if os.getenv("GROUNDING_REPORT_EXPORT_ENABLED","false").strip().lower() not in {"1","true","yes","on"}: raise HTTPException(404,"Grounding 검토 보고서 Export가 비활성화되어 있습니다.")
    report=build_grounding_report_data(data); fmt=str(data.get("format","html")).strip().lower()
    if fmt not in {"html","markdown","md"}: raise HTTPException(400,"지원하는 보고서 형식은 html 또는 markdown입니다.")
    suffix="md" if fmt in {"markdown","md"} else "html"; content=render_grounding_markdown(report) if suffix=="md" else render_grounding_html(report); path=EXPORTS/f"{safe_report_stem(report.title,datetime.now().strftime('%Y%m%d_%H%M%S'))}.{suffix}"; path.write_text(content,encoding="utf-8"); return {"filename":path.name,"url":f"/downloads/{path.name}","format":suffix}
@router.get("/downloads/{filename}")
def download(filename:str):
    safe=Path(filename).name; path=EXPORTS/safe
    if not path.exists(): raise HTTPException(404,"파일을 찾을 수 없습니다.")
    return FileResponse(path,filename=safe)
