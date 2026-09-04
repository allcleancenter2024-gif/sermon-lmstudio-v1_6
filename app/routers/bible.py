from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.application import scripture_facade

router=APIRouter()
class PassageRequest(BaseModel):
    translation: str; language: str = "ko"; reference: str; text: str; license_note: str = ""
class BulkImportRequest(BaseModel):
    items: list[PassageRequest] = Field(min_length=1, max_length=5000)
@router.get("/api/original-coverage")
def original_coverage(reference:str):
    try: return scripture_facade.original_coverage(reference)
    except ValueError as exc: raise HTTPException(400,f"원어 준비상태 확인 실패: {exc}") from exc
@router.get("/api/database/dashboard")
def database_dashboard(): return scripture_facade.database_dashboard()
@router.get("/api/database/integrity")
def database_integrity(): return scripture_facade.database_integrity()
@router.get("/api/compare")
def compare(reference:str): return {"reference":reference,"items":scripture_facade.compare(reference)}
@router.post("/api/passages")
def create_passage(data:PassageRequest):
    try: scripture_facade.create_passage(translation=data.translation,language=data.language,reference=data.reference,text=data.text,license_note=data.license_note)
    except ValueError as exc: raise HTTPException(403,str(exc)) from exc
    return {"ok":True}
@router.post("/api/passages/import")
def bulk_import(data:BulkImportRequest):
    try: return {"ok":True,"imported":scripture_facade.import_passages([x.model_dump() for x in data.items])}
    except ValueError as exc: raise HTTPException(403,str(exc)) from exc
