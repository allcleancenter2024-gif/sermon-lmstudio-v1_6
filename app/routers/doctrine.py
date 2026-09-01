from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core import LMStudioClient, add_doctrine_chunk, rag_stats, recommend_related, register_translation_license, translation_licenses

router=APIRouter()
class DoctrineChunkRequest(BaseModel):
    tradition:str=Field(min_length=2,max_length=100); title:str=Field(min_length=2,max_length=300); section:str=Field(default="",max_length=300); text:str=Field(min_length=2,max_length=12000); source_url:str=Field(default="",max_length=1000); license_note:str=Field(default="",max_length=500)
class TranslationLicenseRequest(BaseModel):
    translation:str=Field(min_length=1,max_length=150); copyright_holder:str=Field(default="",max_length=300); license_status:str=Field(min_length=2,max_length=80); permission_ref:str=Field(default="",max_length=500); source_url:str=Field(default="",max_length=1000); allow_fulltext:bool=False; notes:str=Field(default="",max_length=1000)
@router.post("/api/doctrine")
def create_doctrine(data:DoctrineChunkRequest): return {"ok":True,"id":add_doctrine_chunk(data.model_dump())}
@router.post("/api/translation-licenses")
def create_translation_license(data:TranslationLicenseRequest): register_translation_license(data.model_dump()); return {"ok":True}
@router.get("/api/translation-licenses")
def list_translation_licenses(): return {"items":translation_licenses()}
@router.get("/api/recommend")
def recommend(reference:str,model:str,limit:int=8):
    if model not in rag_stats()["models"]: raise HTTPException(400,"선택한 임베딩 모델의 RAG 인덱스를 먼저 만드세요.")
    try: return {"reference":reference,"model":model,"items":recommend_related(reference,LMStudioClient(),model,min(max(limit,1),20))}
    except (ConnectionError,RuntimeError,ValueError) as exc: raise HTTPException(503,f"관련구절 추천 실패: {exc}") from exc
