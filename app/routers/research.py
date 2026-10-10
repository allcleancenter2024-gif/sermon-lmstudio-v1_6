"""Feature-gated HTTP boundary for the research Section canary."""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.application.section_contracts import SectionRegenerationRequest


class ResearchService(Protocol):
    def generate(self, project_id: int, request: SectionRegenerationRequest) -> dict[str, Any]: ...
    def retry(self, project_id: int, request: SectionRegenerationRequest) -> dict[str, Any]: ...


class ResearchRepository(Protocol):
    def require_ready(self) -> None: ...
    def latest(self, project_id: int, section_type: str) -> dict[str, Any] | None: ...
    def list_versions(self, project_id: int, section_type: str) -> list[dict[str, Any]]: ...


class ResearchSectionRequest(BaseModel):
    context: dict[str, Any]
    evidence: dict[str, Any]
    source_snapshot_id: str = Field(default="", max_length=200)
    attempt: int = Field(default=0, ge=0)
    target_project_id: int | None = Field(default=None, gt=0)
    target_reference: str = Field(default="", max_length=200)
    confirmation: str = Field(default="", max_length=80)


CANARY_CONFIRMATION = "ENABLE-STRUCTURE-CANARY"


def research_canary_enabled(environ: dict[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return env.get("RESEARCH_SECTION_CANARY", "false").strip().lower() in {"1", "true", "yes", "on"}


def _unavailable() -> None:
    raise HTTPException(
        status_code=503,
        detail={
            "code": "research_canary_disabled",
            "message": "연구 Section Canary가 아직 활성화되지 않았습니다.",
        },
    )


def _safe_http_error(exc: Exception) -> HTTPException:
    message = str(exc).lower()
    if "migration is required" in message:
        return HTTPException(503, {"code": "research_schema_unavailable", "message": "연구 저장소가 준비되지 않았습니다."})
    if "builder is not registered" in message:
        return HTTPException(404, {"code": "research_section_not_found", "message": "지원하지 않는 연구 Section입니다."})
    if isinstance(exc, sqlite3.IntegrityError) and "foreign key" in message:
        return HTTPException(404, {"code": "research_project_not_found", "message": "설교 프로젝트를 찾을 수 없습니다."})
    if isinstance(exc, ValueError):
        return HTTPException(400, {"code": "research_request_invalid", "message": "연구 Section 요청 값이 올바르지 않습니다."})
    return HTTPException(503, {"code": "research_section_failed", "message": "연구 Section 처리에 실패했습니다."})


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    """Remove internal exception text before returning a build result."""
    section = dict(result.get("section") or {})
    build = dict(result.get("build") or {})
    status = str(section.get("status") or "")
    if status in {"failed", "insufficient_evidence"}:
        attempt = (section.get("content") or {}).get("attempt", 0)
        code = "research_insufficient_evidence" if status == "insufficient_evidence" else "research_section_failed"
        message = "등록된 중심 본문 근거가 부족합니다." if status == "insufficient_evidence" else "연구 Section 처리에 실패했습니다."
        section["content"] = {"code": code, "message": message, "attempt": attempt}
        build["errors"] = []
    return {"ok": status == "ready", "build": build, "section": section}


def _target_error(project_id: int, section_id: str, data: ResearchSectionRequest, *, require_confirmation: bool) -> HTTPException | None:
    if section_id != "structure":
        return HTTPException(404, {"code": "research_section_not_found", "message": "현재 Canary는 structure Section만 지원합니다."})
    if data.target_project_id != project_id:
        return HTTPException(400, {"code": "research_target_mismatch", "message": "대상 프로젝트 확인이 일치하지 않습니다."})
    reference = str(data.context.get("reference") or "").strip()
    if not reference or data.target_reference.strip() != reference:
        return HTTPException(400, {"code": "research_reference_mismatch", "message": "대상 중심 본문 확인이 일치하지 않습니다."})
    if require_confirmation and data.confirmation != CANARY_CONFIRMATION:
        return HTTPException(409, {"code": "research_confirmation_required", "message": "관리자 확인 후 structure Canary를 실행할 수 있습니다."})
    return None


def build_research_router(
    service: ResearchService,
    repository: ResearchRepository,
    *,
    enabled: bool | None = None,
    auth_db=None,
) -> APIRouter:
    """Build an injectable router without initializing the production DB."""
    router = APIRouter()

    def require_enabled() -> None:
        active = research_canary_enabled() if enabled is None else enabled
        if not active:
            _unavailable()

    def require_admin(request: Request) -> None:
        if auth_db is None:
            return
        from app.auth import is_admin, session_user
        username = session_user(request.cookies.get("sermon_session"))
        if not is_admin(auth_db, username):
            raise HTTPException(403, {"code": "research_admin_required", "message": "관리자만 Research Canary를 실행할 수 있습니다."})

    @router.get("/api/research/canary/status")
    def canary_status():
        """Return a read-only status record for the existing work dashboard."""
        schema_ready = True
        try:
            repository.require_ready()
        except Exception:
            schema_ready = False
        return {
            "ok": True,
            "enabled": research_canary_enabled() if enabled is None else enabled,
            "schema_ready": schema_ready,
            "supported_sections": ["structure"],
            "activation_mode": "admin_dry_run",
            "writes": False,
        }

    @router.get("/api/projects/{project_id}/research/sections/{section_id}")
    def latest_section(project_id: int, section_id: str, request: Request):
        require_enabled()
        # Sermon records do not yet have an owner_id. Until account-to-project
        # ownership is modeled, restrict persisted research to administrators.
        require_admin(request)
        try:
            item = repository.latest(project_id, section_id)
        except Exception as exc:
            raise _safe_http_error(exc) from exc
        if item is None:
            raise HTTPException(404, {"code": "research_section_version_not_found", "message": "저장된 Section 버전이 없습니다."})
        return {"ok": True, "section": item}

    @router.get("/api/projects/{project_id}/research/sections/{section_id}/versions")
    def section_versions(project_id: int, section_id: str, request: Request):
        require_enabled()
        # Match latest_section: authenticated access alone cannot establish
        # project ownership in the current local data model.
        require_admin(request)
        try:
            items = repository.list_versions(project_id, section_id)
        except Exception as exc:
            raise _safe_http_error(exc) from exc
        return {"ok": True, "project_id": project_id, "section_id": section_id, "items": items}

    @router.post("/api/projects/{project_id}/research/sections/{section_id}/dry-run")
    def dry_run_section(project_id: int, section_id: str, data: ResearchSectionRequest, request: Request):
        require_enabled()
        require_admin(request)
        error = _target_error(project_id, section_id, data, require_confirmation=False)
        if error:
            raise error
        return {
            "ok": True,
            "mode": "dry_run",
            "writes_performed": False,
            "project_id": project_id,
            "section_id": section_id,
            "target_reference": data.target_reference.strip(),
            "confirmation_required": True,
            "confirmation": CANARY_CONFIRMATION,
            "writes": {"section": False, "existing_versions_overwritten": False},
            "planned_writes": {"section": True, "existing_versions_overwritten": False},
        }

    @router.post("/api/projects/{project_id}/research/sections/{section_id}/approval-check")
    def approval_check(project_id: int, section_id: str, data: ResearchSectionRequest, request: Request):
        """Evaluate generate prerequisites without invoking a Builder or writing data."""
        require_enabled()
        require_admin(request)
        error = _target_error(project_id, section_id, data, require_confirmation=True)
        if error:
            raise error
        try:
            repository.require_ready()
        except Exception as exc:
            raise _safe_http_error(exc) from exc
        try:
            coverage = float(data.evidence.get("citation_coverage", 0.0))
        except (TypeError, ValueError):
            coverage = -1.0
        checks = {
            "canary_enabled": True,
            "schema_ready": True,
            "target_confirmed": True,
            "source_snapshot_present": bool(data.source_snapshot_id.strip()),
            "citation_coverage_valid": 0 <= coverage <= 1,
            "citation_coverage_present": coverage > 0,
        }
        return {
            "ok": True,
            "section_id": section_id,
            "project_id": project_id,
            "target_reference": data.target_reference.strip(),
            "checks": checks,
            "approval_check_passed": all(checks.values()),
            "generation_activation_required": True,
            "writes_performed": False,
        }

    @router.post("/api/projects/{project_id}/research/sections/{section_id}/generate")
    def generate_section(project_id: int, section_id: str, data: ResearchSectionRequest, request: Request):
        require_enabled()
        require_admin(request)
        error = _target_error(project_id, section_id, data, require_confirmation=True)
        if error:
            raise error
        request = SectionRegenerationRequest(
            section_id=section_id,
            context=dict(data.context),
            evidence=dict(data.evidence),
            source_snapshot_id=data.source_snapshot_id,
            attempt=data.attempt,
        )
        try:
            return _public_result(service.generate(project_id, request))
        except Exception as exc:
            raise _safe_http_error(exc) from exc

    @router.post("/api/projects/{project_id}/research/sections/{section_id}/retry")
    def retry_section(project_id: int, section_id: str, data: ResearchSectionRequest, request: Request):
        require_enabled()
        require_admin(request)
        error = _target_error(project_id, section_id, data, require_confirmation=True)
        if error:
            raise error
        request = SectionRegenerationRequest(
            section_id=section_id,
            context=dict(data.context),
            evidence=dict(data.evidence),
            source_snapshot_id=data.source_snapshot_id,
            attempt=data.attempt,
        )
        try:
            return _public_result(service.retry(project_id, request))
        except Exception as exc:
            raise _safe_http_error(exc) from exc

    return router


__all__ = ["CANARY_CONFIRMATION", "ResearchSectionRequest", "build_research_router", "research_canary_enabled"]
