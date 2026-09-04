from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.application.project_facade import ProjectValidationError, dashboard, detail, save_detail, workflow, workflow_config as project_workflow_config

router = APIRouter()

class ProjectMetaRequest(BaseModel):
    service_date: str = Field(default="", max_length=20)
    series_name: str = Field(default="", max_length=200)
    preacher: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=3000)

@router.get("/api/projects/dashboard")
def projects_dashboard(): return dashboard()

@router.get("/api/workflow/config")
def workflow_config(): return project_workflow_config()

@router.get("/api/sermons/{sermon_id}/versions/{version}/workflow")
def version_workflow(sermon_id:int,version:int):
    try: return workflow(sermon_id,version)
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc

@router.get("/api/projects/{sermon_id}")
def project_detail(sermon_id:int):
    try: return detail(sermon_id)
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc

@router.put("/api/projects/{sermon_id}")
def save_project_detail(sermon_id:int,data:ProjectMetaRequest):
    try: return save_detail(sermon_id, **data.model_dump())
    except ProjectValidationError as exc: raise HTTPException(400,str(exc)) from exc
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc
