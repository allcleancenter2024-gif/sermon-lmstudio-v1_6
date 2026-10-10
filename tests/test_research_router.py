import pytest
from fastapi import HTTPException

from app.routers.research import CANARY_CONFIRMATION, ResearchSectionRequest, build_research_router, research_canary_enabled


class _Repository:
    def __init__(self, error=None): self.error, self.items = error, []
    def require_ready(self):
        if self.error: raise self.error
    def latest(self, project_id, section_type):
        if self.error: raise self.error
        return self.items[0] if self.items else None
    def list_versions(self, project_id, section_type):
        if self.error: raise self.error
        return list(self.items)


class _Service:
    def __init__(self, result=None, error=None): self.result, self.error, self.calls = result, error, []
    def generate(self, project_id, request):
        self.calls.append(("generate", project_id, request))
        if self.error: raise self.error
        return self.result
    def retry(self, project_id, request):
        self.calls.append(("retry", project_id, request))
        if self.error: raise self.error
        return self.result


def _endpoint(router, path, method):
    return next(route.endpoint for route in router.routes if route.path == path and method.upper() in route.methods)


def _request(**overrides):
    values = {"context": {"reference": "테스트 1:1"}, "evidence": {"citation_coverage": 1.0}, "source_snapshot_id": "source-1", "target_project_id": 1, "target_reference": "테스트 1:1", "confirmation": CANARY_CONFIRMATION}
    values.update(overrides)
    return ResearchSectionRequest(**values)


def _ready_result():
    return {
        "build": {"section_id": "structure", "status": "ready", "render_data": {"title": "본문 구조"}, "errors": ()},
        "section": {"id": 1, "project_id": 1, "section_type": "structure", "version": 1, "status": "ready", "content": {"title": "본문 구조"}},
    }


def test_research_canary_flag_defaults_off():
    assert research_canary_enabled({}) is False
    assert research_canary_enabled({"RESEARCH_SECTION_CANARY": "true"}) is True


def test_read_only_canary_status_reports_flag_schema_and_no_writes():
    router = build_research_router(_Service(_ready_result()), _Repository(), enabled=False)
    status = _endpoint(router, "/api/research/canary/status", "GET")()
    assert status == {
        "ok": True,
        "enabled": False,
        "schema_ready": True,
        "supported_sections": ["structure"],
        "activation_mode": "admin_dry_run",
        "writes": False,
    }


def test_disabled_router_returns_unavailable_without_calling_service():
    service = _Service(_ready_result())
    router = build_research_router(service, _Repository(), enabled=False)
    generate = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/generate", "POST")
    with pytest.raises(HTTPException) as error: generate(1, "structure", _request(), None)
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "research_canary_disabled"
    assert service.calls == []


def test_enabled_router_generates_and_retries_with_stable_response_shape():
    service = _Service(_ready_result())
    router = build_research_router(service, _Repository(), enabled=True)
    generate = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/generate", "POST")
    retry = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/retry", "POST")
    generated, retried = generate(1, "structure", _request(), None), retry(1, "structure", _request(), None)
    assert generated["ok"] is True and retried["section"]["version"] == 1
    assert [call[0] for call in service.calls] == ["generate", "retry"]


def test_router_requires_explicit_target_and_confirmation():
    service = _Service(_ready_result())
    router = build_research_router(service, _Repository(), enabled=True)
    dry_run = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/dry-run", "POST")
    generate = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/generate", "POST")

    plan = dry_run(1, "structure", _request(confirmation=""), None)
    assert plan["confirmation_required"] is True
    assert plan["writes_performed"] is False
    assert plan["writes"]["section"] is False
    assert plan["planned_writes"]["section"] is True
    with pytest.raises(HTTPException) as error:
        generate(1, "structure", _request(confirmation=""), None)
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "research_confirmation_required"
    assert service.calls == []


def test_approval_check_is_read_only_and_requires_snapshot_and_coverage():
    router = build_research_router(_Service(_ready_result()), _Repository(), enabled=True)
    check = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/approval-check", "POST")
    passed = check(1, "structure", _request(), None)
    assert passed["approval_check_passed"] is True
    assert passed["generation_activation_required"] is True
    assert passed["writes_performed"] is False
    failed = check(1, "structure", _request(source_snapshot_id="", evidence={"citation_coverage": 0}), None)
    assert failed["approval_check_passed"] is False
    assert failed["checks"]["source_snapshot_present"] is False
    assert failed["checks"]["citation_coverage_present"] is False


def test_router_rejects_target_project_or_reference_mismatch():
    router = build_research_router(_Service(_ready_result()), _Repository(), enabled=True)
    generate = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/generate", "POST")
    with pytest.raises(HTTPException) as project_error:
        generate(1, "structure", _request(target_project_id=2), None)
    with pytest.raises(HTTPException) as reference_error:
        generate(1, "structure", _request(target_reference="다른 본문"), None)
    assert project_error.value.detail["code"] == "research_target_mismatch"
    assert reference_error.value.detail["code"] == "research_reference_mismatch"


def test_router_can_require_admin_for_activation(tmp_path):
    from app.auth import create_session, create_user
    from starlette.requests import Request
    auth_db = tmp_path / "auth.sqlite3"
    create_user(auth_db, "first-admin", "first-admin-password")
    create_user(auth_db, "normal-user", "normal-user-password")
    router = build_research_router(_Service(_ready_result()), _Repository(), enabled=True, auth_db=auth_db)
    generate = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/generate", "POST")
    request = Request({"type": "http", "method": "POST", "path": "/api", "headers": [(b"cookie", f"sermon_session={create_session('normal-user')}".encode())]})
    with pytest.raises(HTTPException) as error:
        generate(1, "structure", _request(), request)
    assert error.value.status_code == 403
    assert error.value.detail["code"] == "research_admin_required"


def test_router_hides_internal_builder_error_text():
    result = {
        "build": {"section_id": "structure", "status": "failed", "render_data": None, "errors": ("RuntimeError: secret path C:/private",)},
        "section": {"status": "failed", "content": {"errors": ["secret path C:/private"], "attempt": 0}},
    }
    router = build_research_router(_Service(result), _Repository(), enabled=True)
    body = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/generate", "POST")(1, "structure", _request(), None)
    assert body["ok"] is False
    assert body["section"]["content"]["code"] == "research_section_failed"
    assert "secret" not in str(body)


def test_router_normalizes_migration_and_request_errors():
    path = "/api/projects/{project_id}/research/sections/{section_id}/generate"
    unavailable = _endpoint(build_research_router(_Service(error=RuntimeError("sermon_sections migration is required")), _Repository(), enabled=True), path, "POST")
    invalid = _endpoint(build_research_router(_Service(error=ValueError("internal validation detail")), _Repository(), enabled=True), path, "POST")
    with pytest.raises(HTTPException) as unavailable_error: unavailable(1, "structure", _request(), None)
    with pytest.raises(HTTPException) as invalid_error: invalid(1, "structure", _request(), None)
    assert unavailable_error.value.status_code == 503
    assert unavailable_error.value.detail["code"] == "research_schema_unavailable"
    assert "migration" not in str(unavailable_error.value.detail)
    assert invalid_error.value.status_code == 400
    assert invalid_error.value.detail["code"] == "research_request_invalid"
    assert "internal validation detail" not in str(invalid_error.value.detail)


def test_router_lists_versions_and_maps_missing_section():
    from starlette.requests import Request

    repository = _Repository()
    router = build_research_router(_Service(_ready_result()), repository, enabled=True)
    versions = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/versions", "GET")
    latest = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}", "GET")
    request = Request({"type": "http", "method": "GET", "path": "/api"})
    assert versions(1, "structure", request)["items"] == []
    with pytest.raises(HTTPException) as missing: latest(1, "structure", request)
    repository.items = [{"id": 1, "version": 1, "status": "ready", "content": {}}]
    assert missing.value.status_code == 404
    assert missing.value.detail["code"] == "research_section_version_not_found"
    assert latest(1, "structure", request)["section"]["version"] == 1


def test_router_requires_admin_to_read_persisted_sections_when_auth_is_configured(tmp_path):
    from fastapi import HTTPException
    from starlette.requests import Request
    from app.auth import create_session, create_user

    auth_db = tmp_path / "auth.sqlite3"
    create_user(auth_db, "first-admin", "first-admin-password")
    create_user(auth_db, "normal-user", "normal-user-password")
    repository = _Repository()
    repository.items = [_ready_result()["section"]]
    router = build_research_router(_Service(_ready_result()), repository, enabled=True, auth_db=auth_db)
    admin_token = create_session("first-admin")
    user_token = create_session("normal-user")

    def request_for(token):
        return Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"cookie", f"sermon_session={token}".encode())],
        })

    latest = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}", "GET")
    versions = _endpoint(router, "/api/projects/{project_id}/research/sections/{section_id}/versions", "GET")
    assert latest(1, "structure", request_for(admin_token))["section"]["version"] == 1
    assert versions(1, "structure", request_for(admin_token))["items"][0]["version"] == 1

    for endpoint in (latest, versions):
        with pytest.raises(HTTPException) as error:
            endpoint(1, "structure", request_for(user_token))
        assert error.value.status_code == 403
        assert error.value.detail["code"] == "research_admin_required"


def test_research_routes_are_not_in_main_public_auth_allowlist():
    from pathlib import Path
    main = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert 'request.url.path.startswith("/api/projects/")' not in main
