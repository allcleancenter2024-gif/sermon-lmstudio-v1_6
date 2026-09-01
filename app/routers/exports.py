from __future__ import annotations
from datetime import datetime
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from app.paths import EXPORTS_DIR
from app.core import (DB_PATH, estimate_minutes, get_project_meta, get_reading_cpm, get_generation_audit, list_sermons, sermon_review_state, sermon_versions, save_sermon)
from app.exporters import dashboard_html, write_docx, write_pdf, write_final_package
from app.exporters_grounding import build_grounding_report_data, render_grounding_html, render_grounding_markdown, safe_report_stem

router=APIRouter(); EXPORTS=EXPORTS_DIR
@router.post("/api/export/markdown")
def export_markdown(data:dict):
    text=str(data.get("text","")).strip()
    if not text: raise HTTPException(400,"내보낼 설교문이 없습니다.")
    path=EXPORTS/f"sermon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"; path.write_text(text,encoding="utf-8"); return {"filename":path.name,"url":f"/downloads/{path.name}"}
@router.post("/api/export/html")
def export_html(data:dict):
    text=str(data.get("text","")).strip()
    if not text: raise HTTPException(400,"내보낼 설교문이 없습니다.")
    path=EXPORTS/f"sermon_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"; path.write_text(dashboard_html(sermon=text,meta=data.get("meta") if isinstance(data.get("meta"),dict) else {},sources=data.get("sources") if isinstance(data.get("sources"),list) else []),encoding="utf-8"); return {"filename":path.name,"url":f"/downloads/{path.name}"}
@router.post("/api/export/word")
def export_word(data:dict):
    text=str(data.get("text","")).strip()
    if not text: raise HTTPException(400,"내보낼 설교문이 없습니다.")
    path=EXPORTS/f"sermon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    try: write_docx(path,sermon=text,meta=data.get("meta") if isinstance(data.get("meta"),dict) else {})
    except RuntimeError as exc: raise HTTPException(503,str(exc)) from exc
    return {"filename":path.name,"url":f"/downloads/{path.name}"}
@router.post("/api/export/pdf")
def export_pdf(data:dict):
    text=str(data.get("text","")).strip()
    if not text: raise HTTPException(400,"내보낼 설교문이 없습니다.")
    path=EXPORTS/f"sermon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    try: write_pdf(path,sermon=text,meta=data.get("meta") if isinstance(data.get("meta"),dict) else {},sources=data.get("sources") if isinstance(data.get("sources"),list) else [])
    except RuntimeError as exc: raise HTTPException(503,str(exc)) from exc
    return {"filename":path.name,"url":f"/downloads/{path.name}"}
@router.post("/api/export/grounding")
def export_grounding(data:dict):
    if os.getenv("GROUNDING_REPORT_EXPORT_ENABLED","false").strip().lower() not in {"1","true","yes","on"}: raise HTTPException(404,"Grounding 검토 보고서 Export가 비활성화되어 있습니다.")
    report=build_grounding_report_data(data); fmt=str(data.get("format","html")).strip().lower()
    if fmt not in {"html","markdown","md"}: raise HTTPException(400,"지원하는 보고서 형식은 html 또는 markdown입니다.")
    suffix="md" if fmt in {"markdown","md"} else "html"; content=render_grounding_markdown(report) if suffix=="md" else render_grounding_html(report); path=EXPORTS/f"{safe_report_stem(report.title,datetime.now().strftime('%Y%m%d_%H%M%S'))}.{suffix}"; path.write_text(content,encoding="utf-8"); return {"filename":path.name,"url":f"/downloads/{path.name}","format":suffix}
@router.get("/downloads/{filename}")
def download(filename:str):
    safe=Path(filename).name; path=EXPORTS/safe
    if not path.exists(): raise HTTPException(404,"파일을 찾을 수 없습니다.")
    return FileResponse(path,filename=safe)
