from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core import add_passage, bible_database_dashboard, bible_database_integrity, compare_reference, import_items, original_language_coverage

router=APIRouter()
class PassageRequest(BaseModel):
    translation: str; language: str = "ko"; reference: str; text: str; license_note: str = ""
class BulkImportRequest(BaseModel):
    items: list[PassageRequest] = Field(min_length=1, max_length=5000)
@router.get("/api/original-coverage")
def original_coverage(reference:str):
    try: return original_language_coverage(reference)
    except ValueError as exc: raise HTTPException(400,f"원어 준비상태 확인 실패: {exc}") from exc
@router.get("/api/database/dashboard")
def database_dashboard(): return bible_database_dashboard()
@router.get("/api/database/integrity")
def database_integrity(): return bible_database_integrity()
@router.get("/api/compare")
def compare(reference:str): return {"reference":reference,"items":compare_reference(reference)}
@router.post("/api/passages")
def create_passage(data:PassageRequest):
    try: add_passage(data.translation,data.language,data.reference,data.text,data.license_note)
    except ValueError as exc: raise HTTPException(403,str(exc)) from exc
    return {"ok":True}
@router.post("/api/passages/import")
def bulk_import(data:BulkImportRequest):
    try: return {"ok":True,"imported":import_items([x.model_dump() for x in data.items])}
    except ValueError as exc: raise HTTPException(403,str(exc)) from exc
