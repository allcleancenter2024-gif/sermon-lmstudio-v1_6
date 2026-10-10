"""HTTP boundary for explicitly managed sermon collaborators."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.collaboration_service import SermonCollaborationService
from app.auth import is_admin, list_users, session_user, user_exists


class AssignmentRequest(BaseModel):
    author_id: str = Field(min_length=3, max_length=80)
    reviewer_id: str = Field(min_length=3, max_length=80)
    approver_id: str = Field(min_length=3, max_length=80)
    expected_revision: int = Field(ge=0)


def build_collaboration_router(*, repository, auth_db, auth_enabled: bool = True) -> APIRouter:
    router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])
    service = SermonCollaborationService(
        repository,
        user_exists=lambda username: user_exists(auth_db, username),
        is_admin=lambda username: is_admin(auth_db, username),
    )

    def require_user(request: Request) -> str:
        if not auth_enabled:
            raise HTTPException(503, {"code": "collaboration_auth_required", "message": "협업 기능에는 계정 인증이 필요합니다."})
        username = session_user(request.cookies.get("sermon_session"))
        if not username or not user_exists(auth_db, username):
            raise HTTPException(401, {"code": "authentication_required", "message": "로그인이 필요합니다."})
        return username

    def require_admin(request: Request) -> str:
        username = require_user(request)
        if not is_admin(auth_db, username):
            raise HTTPException(403, {"code": "collaboration_admin_required", "message": "관리자만 계정과 담당자 배정을 관리할 수 있습니다."})
        return username

    @router.get("/users")
    def users(request: Request):
        require_admin(request)
        return {"items": list_users(auth_db)}

    @router.get("/assignments")
    def my_assignments(request: Request):
        username = require_user(request)
        try:
            return {"items": repository.list_for_user(username)}
        except RuntimeError as exc:
            if "migration is required" in str(exc):
                raise HTTPException(503, {"code": "collaboration_schema_unavailable", "message": "협업 저장소가 아직 활성화되지 않았습니다."}) from exc
            raise

    @router.get("/sermons/{sermon_id}/assignment")
    def sermon_assignment(sermon_id: int, request: Request):
        require_admin(request)
        try:
            return {"assignment": repository.get_assignment(sermon_id)}
        except RuntimeError as exc:
            if "migration is required" in str(exc):
                raise HTTPException(503, {"code": "collaboration_schema_unavailable", "message": "협업 저장소가 아직 활성화되지 않았습니다."}) from exc
            raise

    @router.put("/sermons/{sermon_id}/assignment")
    def assign(sermon_id: int, data: AssignmentRequest, request: Request):
        username = require_user(request)
        try:
            result = service.assign(
                sermon_id=sermon_id,
                author_id=data.author_id,
                reviewer_id=data.reviewer_id,
                approver_id=data.approver_id,
                actor_id=username,
                expected_revision=data.expected_revision,
            )
            return {"ok": True, "assignment": result}
        except PermissionError as exc:
            raise HTTPException(403, {"code": "collaboration_admin_required", "message": str(exc)}) from exc
        except ValueError as exc:
            if str(exc) == "expected_revision_mismatch":
                raise HTTPException(409, {"code": "assignment_revision_conflict", "message": "배정 정보가 변경되었습니다. 새 정보를 불러와 다시 시도하세요."}) from exc
            if "프로젝트를 찾을 수 없습니다" in str(exc):
                raise HTTPException(404, {"code": "sermon_not_found", "message": "설교 프로젝트를 찾을 수 없습니다."}) from exc
            raise HTTPException(400, {"code": "assignment_invalid", "message": str(exc)}) from exc
        except RuntimeError as exc:
            if "migration is required" in str(exc):
                raise HTTPException(503, {"code": "collaboration_schema_unavailable", "message": "협업 저장소가 아직 활성화되지 않았습니다."}) from exc
            raise

    return router


__all__ = ["AssignmentRequest", "build_collaboration_router"]
