from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.core import DEFAULT_SERMON_MINUTES, SUPPORTED_SERMON_MINUTES, get_project_meta, get_reading_cpm, list_sermons, project_dashboard, sermon_workflow_status, update_project_meta
from app.version import APP_VERSION, app_version_major

router = APIRouter()

class ProjectMetaRequest(BaseModel):
    service_date: str = Field(default="", max_length=20)
    series_name: str = Field(default="", max_length=200)
    preacher: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=3000)

@router.get("/api/projects/dashboard")
def projects_dashboard(): return project_dashboard()

@router.get("/api/workflow/config")
def workflow_config():
    reading_cpm=get_reading_cpm()
    return {"version":app_version_major(),"app_version":APP_VERSION,"minutes":list(SUPPORTED_SERMON_MINUTES),"default_minutes":DEFAULT_SERMON_MINUTES,"reading_cpm":reading_cpm,"target_characters":{str(m):m*reading_cpm for m in SUPPORTED_SERMON_MINUTES},"steps":["brief","bible","languages","draft","evidence","review","final"]}

@router.get("/api/sermons/{sermon_id}/versions/{version}/workflow")
def version_workflow(sermon_id:int,version:int):
    try: return sermon_workflow_status(sermon_id,version)
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc

@router.get("/api/projects/{sermon_id}")
def project_detail(sermon_id:int):
    if not any(item["id"]==sermon_id for item in list_sermons()): raise HTTPException(404,"설교 프로젝트를 찾을 수 없습니다.")
    return get_project_meta(sermon_id)

@router.put("/api/projects/{sermon_id}")
def save_project_detail(sermon_id:int,data:ProjectMetaRequest):
    if data.service_date:
        try: datetime.strptime(data.service_date,"%Y-%m-%d")
        except ValueError as exc: raise HTTPException(400,"예배일은 YYYY-MM-DD 형식으로 입력하세요.") from exc
    try: return {"ok":True,**update_project_meta(sermon_id,**data.model_dump())}
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
