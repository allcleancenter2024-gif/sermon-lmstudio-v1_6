"""Project application boundary.

This facade deliberately delegates persistence to the existing core and
repository-backed functions.  It gives routers one application contract
without moving database schema or breaking legacy app.main imports.
"""

from datetime import datetime

from app.paths import RESOURCE_ROOT
from app.core import (
    DEFAULT_SERMON_MINUTES,
    SUPPORTED_SERMON_MINUTES,
    get_project_meta,
    get_reading_cpm,
    list_sermons,
    project_dashboard,
    sermon_workflow_status,
    update_project_meta,
)
from app.version import APP_VERSION, app_version_major
from app.project_summary import build_project_summary


class ProjectValidationError(ValueError):
    """Input validation error that callers expose as HTTP 400."""


def dashboard() -> dict:
    return project_dashboard()


def summary() -> dict:
    """Return the legacy project summary through the project boundary."""
    return build_project_summary(RESOURCE_ROOT, APP_VERSION)


def workflow_config() -> dict:
    reading_cpm = get_reading_cpm()
    return {
        "version": app_version_major(),
        "app_version": APP_VERSION,
        "minutes": list(SUPPORTED_SERMON_MINUTES),
        "default_minutes": DEFAULT_SERMON_MINUTES,
        "reading_cpm": reading_cpm,
        "target_characters": {str(m): m * reading_cpm for m in SUPPORTED_SERMON_MINUTES},
        "steps": ["brief", "bible", "languages", "draft", "evidence", "review", "final"],
    }


def workflow(sermon_id: int, version: int) -> dict:
    return sermon_workflow_status(sermon_id, version)


def detail(sermon_id: int) -> dict:
    if not any(item["id"] == sermon_id for item in list_sermons()):
        raise ValueError("설교 프로젝트를 찾을 수 없습니다.")
    return get_project_meta(sermon_id)


def save_detail(sermon_id: int, *, service_date: str, series_name: str, preacher: str, notes: str) -> dict:
    if service_date:
        try:
            datetime.strptime(service_date, "%Y-%m-%d")
        except ValueError as exc:
            raise ProjectValidationError("예배일은 YYYY-MM-DD 형식으로 입력하세요.") from exc
    return {"ok": True, **update_project_meta(
        sermon_id,
        service_date=service_date,
        series_name=series_name,
        preacher=preacher,
        notes=notes,
    )}
