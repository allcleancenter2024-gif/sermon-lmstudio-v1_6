"""Read-only HTTP contract checks for the assembled FastAPI application.

The environment does not include the optional ``httpx2`` package expected by
this Starlette version, so the tests use a tiny ASGI harness instead of
installing a dependency or changing the application runtime.
"""

import asyncio
import json

from app.main import app


def _request(path: str) -> dict:
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    async def run():
        await app(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [],
                "server": ("testserver", 80),
                "client": ("testclient", 1234),
            },
            receive,
            send,
        )

    asyncio.run(run())
    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return {
        "status_code": start["status"],
        "headers": {key.decode().lower(): value.decode() for key, value in start["headers"]},
        "json": json.loads(body.decode("utf-8")),
    }


def test_runtime_and_auth_status_are_public_http_contracts():
    runtime = _request("/api/runtime")
    assert runtime["status_code"] == 200
    runtime_body = runtime["json"]
    assert runtime_body["runtime_id"] == "sermon-lmstudio-local"
    assert runtime_body["app_version"]
    assert runtime_body["lmstudio_url"].startswith("http://127.0.0.1:")
    assert runtime["headers"]["x-sermon-app-version"] == runtime_body["app_version"]

    auth_status = _request("/api/auth/status")
    assert auth_status["status_code"] == 200
    assert set(("authenticated", "username", "setup_required")) <= auth_status["json"].keys()


def test_health_and_project_data_apis_remain_auth_protected_http_contracts():
    for path in ("/api/health", "/api/projects/dashboard", "/api/project-summary"):
        response = _request(path)
        assert response["status_code"] == 401
        assert response["json"] == {"detail": "로그인이 필요합니다.", "code": "auth_required"}
