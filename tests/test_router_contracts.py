"""Stable external contracts for the first application routers.

These tests intentionally inspect the router boundary instead of importing
``app.main``. Importing main initializes the production database and local
runtime, which is not needed to verify URL and response-shape contracts.
"""

from pathlib import Path

import pytest
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_health_router_contract_keeps_public_runtime_and_health_shapes():
    router = _read("app/routers/health.py")

    assert '@router.get("/api/runtime")' in router
    assert '@router.get("/api/health")' in router
    for key in ("runtime_id", "app_version", "supported_minutes", "default_minutes", "lmstudio_url"):
        assert f'"{key}"' in router
    for key in ("connected", "models", "generation_models", "embedding_models", "database", "rag", "message"):
        assert f'"{key}"' in router
    assert "http://0.0.0.0" not in router


def test_settings_router_contract_keeps_configuration_and_validation_boundaries():
    router = _read("app/routers/settings.py")

    for route in (
        '@router.get("/api/settings/github")',
        '@router.put("/api/settings/github")',
        '@router.get("/api/settings/lmstudio")',
        '@router.put("/api/settings/lmstudio")',
        '@router.get("/api/settings/reading-speed")',
        '@router.put("/api/settings/reading-speed")',
        '@router.post("/api/settings/reading-speed/calibrate")',
    ):
        assert route in router
    assert 'Field(ge=180, le=600)' in router
    assert 'Field(default="http://127.0.0.1:12345/v1"' in router
    assert 'raise HTTPException(400' in router
    assert "http://0.0.0.0" not in router


def test_projects_router_contract_keeps_urls_error_mapping_and_workflow_keys():
    router = _read("app/routers/projects.py")

    for route in (
        '@router.get("/api/projects/dashboard")',
        '@router.get("/api/project-summary")',
        '@router.get("/api/workflow/config")',
        '@router.get("/api/sermons/{sermon_id}/versions/{version}/workflow")',
        '@router.get("/api/projects/{sermon_id}")',
        '@router.put("/api/projects/{sermon_id}")',
    ):
        assert route in router
    assert "raise HTTPException(404" in router
    assert "raise HTTPException(400" in router
    assert '"brief", "bible", "languages", "draft", "evidence", "review", "final"' in _read(
        "app/application/project_facade.py"
    )


def _runtime_request() -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/runtime",
        "headers": [],
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 1234),
    })


def test_health_runtime_function_keeps_local_runtime_identity():
    from app.routers import health

    result = health.runtime_info(_runtime_request())

    assert result["runtime_id"] == "sermon-lmstudio-local"
    assert result["app_version"]
    assert result["local_url"] == "http://testserver"
    assert result["lmstudio_url"].startswith("http://127.0.0.1:")


def test_health_function_keeps_success_response_when_model_catalog_is_available(monkeypatch):
    from app.routers import health

    class FakeClient:
        def model_catalog(self):
            return {
                "models": ["local-model"],
                "generation_models": ["local-model"],
                "embedding_models": [],
                "source": "openai_compatible",
                "openai_models_ok": True,
                "openai_error": "",
            }

    monkeypatch.setattr(health, "LMStudioClient", FakeClient)
    monkeypatch.setattr(health, "db_stats", lambda: {"passages": 3})
    monkeypatch.setattr(health, "rag_stats", lambda: {"vectors": 2})

    result = health.health()

    assert result["connected"] is True
    assert result["models"] == ["local-model"]
    assert result["database"] == {"passages": 3}
    assert result["rag"] == {"vectors": 2}
    assert result["message"] == ""


def test_health_function_keeps_degraded_response_when_lmstudio_is_unavailable(monkeypatch):
    from app.routers import health

    class OfflineClient:
        def model_catalog(self):
            raise ConnectionError("LM Studio unavailable")

    monkeypatch.setattr(health, "LMStudioClient", OfflineClient)
    monkeypatch.setattr(health, "db_stats", lambda: {"passages": 0})
    monkeypatch.setattr(health, "rag_stats", lambda: {"vectors": 0})

    result = health.health()

    assert result["connected"] is False
    assert result["source"] == "unavailable"
    assert result["models"] == []
    assert result["database"] == {"passages": 0}
    assert result["rag"] == {"vectors": 0}
    assert result["message"] == "LM Studio unavailable"


def test_settings_router_keeps_reading_speed_validation_and_update_contract(monkeypatch):
    from app.routers import settings

    assert settings.ReadingSpeedRequest(chars_per_minute=180).chars_per_minute == 180
    assert settings.ReadingSpeedRequest(chars_per_minute=600).chars_per_minute == 600
    with pytest.raises(Exception):
        settings.ReadingSpeedRequest(chars_per_minute=179)

    monkeypatch.setattr(settings, "get_reading_cpm", lambda: 300)
    monkeypatch.setattr(settings, "set_reading_cpm", lambda value: value)
    assert settings.reading_speed() == {"chars_per_minute": 300}
    assert settings.update_reading_speed(settings.ReadingSpeedRequest(chars_per_minute=360)) == {
        "ok": True, "chars_per_minute": 360,
    }


def test_settings_router_keeps_lmstudio_success_and_connection_failure_contract(monkeypatch):
    from app.routers import settings

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def model_catalog(self):
            return {
                "models": ["local-model"],
                "generation_models": ["local-model"],
                "embedding_models": [],
                "source": "openai_compatible",
            }

    monkeypatch.setattr(settings, "set_lmstudio_url", lambda value: value.rstrip("/"))
    monkeypatch.setattr(settings, "get_lmstudio_url", lambda: "http://127.0.0.1:12345/v1")
    monkeypatch.setattr(settings, "LMStudioClient", FakeClient)

    result = settings.update_lmstudio_settings(
        settings.LMStudioSettingsRequest(base_url="http://127.0.0.1:12345/v1/")
    )
    assert result["ok"] is True
    assert result["connected"] is True
    assert result["base_url"] == "http://127.0.0.1:12345/v1"
    assert result["models"] == ["local-model"]

    class OfflineClient(FakeClient):
        def model_catalog(self):
            raise ConnectionError("LM Studio unavailable")

    monkeypatch.setattr(settings, "LMStudioClient", OfflineClient)
    degraded = settings.update_lmstudio_settings(
        settings.LMStudioSettingsRequest(base_url="http://127.0.0.1:12345/v1")
    )
    assert degraded == {
        "ok": True,
        "connected": False,
        "base_url": "http://127.0.0.1:12345/v1",
        "models": [],
        "message": "LM Studio unavailable",
    }


def test_settings_router_maps_invalid_lmstudio_url_to_http_400(monkeypatch):
    from fastapi import HTTPException
    from app.routers import settings

    def reject_url(value):
        raise ValueError("localhost 주소만 허용됩니다.")

    monkeypatch.setattr(settings, "set_lmstudio_url", reject_url)
    try:
        settings.update_lmstudio_settings(
            settings.LMStudioSettingsRequest(base_url="http://example.com/v1")
        )
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "localhost 주소만 허용됩니다."
    else:
        raise AssertionError("invalid LM Studio URL must map to HTTP 400")


def test_projects_router_executes_facade_contracts_without_database(monkeypatch):
    from app.routers import projects

    dashboard = {"projects": [], "summary": {"total": 0}, "reading_cpm": 330}
    workflow_config = {"steps": ["brief", "bible", "languages", "draft", "evidence", "review", "final"]}
    monkeypatch.setattr(projects, "dashboard", lambda: dashboard)
    monkeypatch.setattr(projects, "summary", lambda: {"ok": True})
    monkeypatch.setattr(projects, "project_workflow_config", lambda: workflow_config)

    assert projects.projects_dashboard() is dashboard
    assert projects.project_summary() == {"ok": True}
    assert projects.workflow_config() is workflow_config


def test_projects_router_maps_workflow_and_detail_errors_to_http_404(monkeypatch):
    from fastapi import HTTPException
    from app.routers import projects

    def missing(*args, **kwargs):
        raise ValueError("설교 버전을 찾을 수 없습니다.")

    monkeypatch.setattr(projects, "workflow", missing)
    with pytest.raises(HTTPException) as workflow_error:
        projects.version_workflow(7, 2)
    assert workflow_error.value.status_code == 404

    monkeypatch.setattr(projects, "detail", missing)
    with pytest.raises(HTTPException) as detail_error:
        projects.project_detail(7)
    assert detail_error.value.status_code == 404


def test_projects_router_maps_metadata_validation_and_not_found_errors(monkeypatch):
    from fastapi import HTTPException
    from app.routers import projects

    request = projects.ProjectMetaRequest(
        service_date="2026-10-01", series_name="시리즈", preacher="설교자", notes="메모"
    )
    monkeypatch.setattr(projects, "save_detail", lambda sermon_id, **data: {"sermon_id": sermon_id, **data})
    assert projects.save_project_detail(7, request)["sermon_id"] == 7

    def invalid(*args, **kwargs):
        raise projects.ProjectValidationError("예배일은 YYYY-MM-DD 형식으로 입력하세요.")

    monkeypatch.setattr(projects, "save_detail", invalid)
    with pytest.raises(HTTPException) as validation_error:
        projects.save_project_detail(7, request)
    assert validation_error.value.status_code == 400

    def missing(*args, **kwargs):
        raise ValueError("설교 프로젝트를 찾을 수 없습니다.")

    monkeypatch.setattr(projects, "save_detail", missing)
    with pytest.raises(HTTPException) as not_found_error:
        projects.save_project_detail(7, request)
    assert not_found_error.value.status_code == 404


def test_main_auth_middleware_contract_keeps_runtime_public_and_data_apis_protected():
    main = _read("app/main.py")

    assert '@app.middleware("http")' in main
    assert '"/api/runtime"' in main
    assert '"/api/auth/status"' in main
    assert '"/favicon.ico"' in main
    assert '@app.get("/favicon.ico"' in main
    assert '"/api/auth/login"' in main
    assert '"/api/auth/register"' in main
    assert 'status_code=401' in main
    assert '"code": "auth_required"' in main
    assert 'request.url.path == "/api/health"' not in main
