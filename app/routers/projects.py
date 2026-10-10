from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from app.application.project_facade import DB_PATH, ProjectValidationError, dashboard, detail, save_detail, summary, workflow, workflow_config as project_workflow_config
from app.auth import is_admin, session_user
from app.paths import USER_ROOT
from app.repositories.collaboration import SermonCollaborationRepository

router = APIRouter()
_collaboration_repository = SermonCollaborationRepository(DB_PATH)
_auth_db = USER_ROOT / "auth.sqlite3"

class ProjectMetaRequest(BaseModel):
    service_date: str = Field(default="", max_length=20)
    series_name: str = Field(default="", max_length=200)
    preacher: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=3000)

@router.get("/api/projects/dashboard")
def _projects_dashboard_http(request: Request):
    result = dashboard()
    actor = session_user(request.cookies.get("sermon_session")) if request else None
    if _collaboration_repository.schema_ready() and actor and not is_admin(_auth_db, actor):
        visible_ids = {int(item["sermon_id"]) for item in _collaboration_repository.list_for_user(actor)}
        projects = [item for item in result.get("projects", []) if int(item["sermon_id"]) in visible_ids]
        counts = {state: sum(1 for item in projects if item.get("state") == state)
                  for state in ("unreviewed", "comment", "changes_requested", "approved", "locked")}
        result = {**result, "projects": projects, "summary": {"total": len(projects), **counts}}
    return result


def projects_dashboard():
    """Compatibility facade retained for direct callers and older tests."""
    return dashboard()

@router.get("/api/project-summary")
def project_summary(): return summary()

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
