from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import sqlite3
from app.core import DB_PATH, LMStudioClient, add_doctrine_chunk, rag_stats, recommend_related, register_translation_license, translation_licenses
from app.auth import is_admin, session_user
from app.doctrine_workflow import fetch_indexable_doctrine_chunks, transition_document
from app.doctrine_rag import build_approved_doctrine_index, search_approved_doctrine
from app.paths import USER_ROOT

router=APIRouter()
class DoctrineChunkRequest(BaseModel):
    tradition:str=Field(min_length=2,max_length=100); title:str=Field(min_length=2,max_length=300); section:str=Field(default="",max_length=300); text:str=Field(min_length=2,max_length=12000); source_url:str=Field(default="",max_length=1000); license_note:str=Field(default="",max_length=500)
class TranslationLicenseRequest(BaseModel):
    translation:str=Field(min_length=1,max_length=150); copyright_holder:str=Field(default="",max_length=300); license_status:str=Field(min_length=2,max_length=80); permission_ref:str=Field(default="",max_length=500); source_url:str=Field(default="",max_length=1000); allow_fulltext:bool=False; notes:str=Field(default="",max_length=1000)

class DoctrineReviewRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str = Field(default="", max_length=2000)

class DoctrineIndexRequest(BaseModel):
    model: str = Field(min_length=1, max_length=300)

class DoctrineLicenseReviewRequest(BaseModel):
    license_status: str = Field(pattern="^(PERMISSION_REQUIRED|VERIFIED|BLOCKED)$")
    reviewer: str = Field(min_length=1, max_length=100)
    permission_ref: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=2000)

class DoctrineSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=3000)
    model: str = Field(min_length=1, max_length=300)
    denomination_code: str = Field(min_length=1, max_length=40)
    limit: int = Field(default=6, ge=1, le=50)
    include_common: bool = True

def _require_admin(request: Request) -> str:
    username = session_user(request.cookies.get("sermon_session"))
    if not is_admin(USER_ROOT / "auth.sqlite3", username):
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return username or ""
@router.post("/api/doctrine")
def create_doctrine(data:DoctrineChunkRequest, request: Request):
    _require_admin(request)
    return {"ok":True,"id":add_doctrine_chunk(data.model_dump())}

@router.get("/api/admin/doctrine/indexable")
def list_indexable_doctrine(request: Request):
    _require_admin(request)
    return {"items": fetch_indexable_doctrine_chunks(DB_PATH)}

@router.post("/api/admin/doctrine/sources/{source_id}/license-review")
def review_doctrine_license(source_id: int, data: DoctrineLicenseReviewRequest, request: Request):
    actor = _require_admin(request)
    if data.reviewer.strip() != actor:
        raise HTTPException(403, "로그인 계정과 검토자 계정이 일치해야 합니다.")
    active = 1 if data.license_status == "VERIFIED" else 0
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute("SELECT id FROM doctrine_sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise HTTPException(404, "교단 자료원을 찾지 못했습니다.")
        con.execute("UPDATE doctrine_sources SET license_status=?, active=?, permission_ref=?, license_reviewed_by=?, license_reviewed_at=?, license_review_note=?, updated_at=? WHERE id=?", (data.license_status, active, data.permission_ref.strip(), actor, reviewed_at, data.note.strip(), reviewed_at, source_id))
    return {"ok": True, "source_id": source_id, "license_status": data.license_status, "active": bool(active), "reviewed_by": actor, "reviewed_at": reviewed_at}

@router.post("/api/admin/doctrine/documents/{document_id}/review")
def review_doctrine_document(document_id: int, data: DoctrineReviewRequest, request: Request):
    actor = _require_admin(request)
    if data.reviewer.strip() != actor:
        raise HTTPException(403, "로그인 계정과 검토자 계정이 일치해야 합니다.")
    try:
        return {"ok": True, **transition_document(document_id, "APPROVED", actor, data.comment, DB_PATH)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@router.post("/api/admin/doctrine/reindex")
def reindex_approved_doctrine(data: DoctrineIndexRequest, request: Request):
    _require_admin(request)
    try:
        return {"ok": True, **build_approved_doctrine_index(LMStudioClient(), data.model, DB_PATH)}
    except (ConnectionError, RuntimeError, ValueError) as exc:
        raise HTTPException(503, f"승인 교리 색인 실패: {exc}") from exc

@router.post("/api/doctrine/search")
def search_doctrine_v2(data: DoctrineSearchRequest):
    try:
        return {"items": search_approved_doctrine(data.query, LMStudioClient(), data.model, data.denomination_code, DB_PATH, data.limit, data.include_common)}
    except (ConnectionError, RuntimeError, ValueError) as exc:
        raise HTTPException(503, f"교단 교리 검색 실패: {exc}") from exc
@router.post("/api/translation-licenses")
def create_translation_license(data:TranslationLicenseRequest): register_translation_license(data.model_dump()); return {"ok":True}
@router.get("/api/translation-licenses")
def list_translation_licenses(): return {"items":translation_licenses()}
@router.get("/api/recommend")
def recommend(reference:str,model:str,limit:int=8):
    if model not in rag_stats()["models"]: raise HTTPException(400,"선택한 임베딩 모델의 RAG 인덱스를 먼저 만드세요.")
    try: return {"reference":reference,"model":model,"items":recommend_related(reference,LMStudioClient(),model,min(max(limit,1),20))}
    except (ConnectionError,RuntimeError,ValueError) as exc: raise HTTPException(503,f"관련구절 추천 실패: {exc}") from exc
