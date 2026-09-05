from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app.auth import is_admin, session_user
from app.application import doctrine_facade
from app.application.doctrine_facade import DB_PATH
from app.paths import USER_ROOT
from app.kmc_reference import build_kmc_final_checklist, build_kmc_operational_report, compare_kmc_reference_metadata, kmc_reference_review_gate, list_kmc_reference_check_logs, probe_kmc_reference_headers, record_kmc_review_decisions

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

class KmcReviewDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(ACKNOWLEDGED|REJECTED)$")
    comment: str = Field(default="", max_length=2000)

def _require_admin(request: Request) -> str:
    username = session_user(request.cookies.get("sermon_session"))
    if not is_admin(USER_ROOT / "auth.sqlite3", username):
        raise HTTPException(403, "관리자 권한이 필요합니다.")
    return username or ""
@router.post("/api/doctrine")
def create_doctrine(data:DoctrineChunkRequest, request: Request):
    _require_admin(request)
    return {"ok":True,"id":doctrine_facade.create_chunk(data.model_dump())}

@router.get("/api/admin/doctrine/indexable")
def list_indexable_doctrine(request: Request):
    _require_admin(request)
    return {"items": doctrine_facade.indexable_chunks(DB_PATH)}

@router.get("/api/doctrine/kmc/reference-comparison")
def compare_kmc_references():
    return compare_kmc_reference_metadata(DB_PATH)

@router.post("/api/doctrine/kmc/reference-check")
def check_kmc_references():
    return probe_kmc_reference_headers(DB_PATH)

@router.get("/api/admin/doctrine/kmc/check-logs")
def list_kmc_check_logs(request: Request, limit: int = 30):
    _require_admin(request)
    return {"items": list_kmc_reference_check_logs(DB_PATH, limit)}

@router.get("/api/admin/doctrine/kmc/review-gate")
def get_kmc_review_gate(request: Request):
    _require_admin(request)
    return kmc_reference_review_gate(DB_PATH)

@router.get("/api/admin/doctrine/kmc/operational-report")
def get_kmc_operational_report(request: Request):
    _require_admin(request)
    return build_kmc_operational_report(DB_PATH)

@router.post("/api/admin/doctrine/kmc/review-decisions")
def record_kmc_review(data: KmcReviewDecisionRequest, request: Request):
    actor = _require_admin(request)
    return record_kmc_review_decisions(DB_PATH, actor, data.decision, data.comment)

@router.get("/api/admin/doctrine/kmc/final-checklist")
def get_kmc_final_checklist(request: Request):
    _require_admin(request)
    return build_kmc_final_checklist(DB_PATH)

@router.post("/api/admin/doctrine/sources/{source_id}/license-review")
def review_doctrine_license(source_id: int, data: DoctrineLicenseReviewRequest, request: Request):
    actor = _require_admin(request)
    if data.reviewer.strip() != actor:
        raise HTTPException(403, "로그인 계정과 검토자 계정이 일치해야 합니다.")
    try:
        return doctrine_facade.review_license(source_id, license_status=data.license_status, reviewer=actor, permission_ref=data.permission_ref, note=data.note, db_path=DB_PATH)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc

@router.post("/api/admin/doctrine/documents/{document_id}/review")
def review_doctrine_document(document_id: int, data: DoctrineReviewRequest, request: Request):
    actor = _require_admin(request)
    if data.reviewer.strip() != actor:
        raise HTTPException(403, "로그인 계정과 검토자 계정이 일치해야 합니다.")
    try:
        return {"ok": True, **doctrine_facade.review_document(document_id, actor=actor, comment=data.comment, db_path=DB_PATH)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@router.post("/api/admin/doctrine/reindex")
def reindex_approved_doctrine(data: DoctrineIndexRequest, request: Request):
    _require_admin(request)
    try:
        return {"ok": True, **doctrine_facade.reindex(data.model, DB_PATH)}
    except (ConnectionError, RuntimeError, ValueError) as exc:
        raise HTTPException(503, f"승인 교리 색인 실패: {exc}") from exc

@router.post("/api/doctrine/search")
def search_doctrine_v2(data: DoctrineSearchRequest):
    try:
        return {"items": doctrine_facade.search(data.query, data.model, data.denomination_code, data.limit, data.include_common, DB_PATH)}
    except (ConnectionError, RuntimeError, ValueError) as exc:
        raise HTTPException(503, f"교단 교리 검색 실패: {exc}") from exc
@router.post("/api/translation-licenses")
def create_translation_license(data:TranslationLicenseRequest): doctrine_facade.create_license(data.model_dump()); return {"ok":True}
@router.get("/api/translation-licenses")
def list_translation_licenses(): return {"items":doctrine_facade.list_licenses()}
@router.get("/api/recommend")
def recommend(reference:str,model:str,limit:int=8):
    if model not in doctrine_facade.available_models(): raise HTTPException(400,"선택한 임베딩 모델의 RAG 인덱스를 먼저 만드세요.")
    try: return {"reference":reference,"model":model,"items":doctrine_facade.recommend(reference,model,limit)}
    except (ConnectionError,RuntimeError,ValueError) as exc: raise HTTPException(503,f"관련구절 추천 실패: {exc}") from exc
