"""Run an isolated localhost HTTP smoke test for the Research Section canary."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(url: str, *, method: str = "GET", payload: dict | None = None, opener=None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        response = opener.open(request, timeout=10) if opener else urllib.request.urlopen(request, timeout=10)
        return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _start(root: Path, port: int, enabled: bool) -> subprocess.Popen:
    env = dict(os.environ)
    env.update({
        "SERMON_USER_ROOT": str(root),
        "RESEARCH_SECTION_CANARY": "true" if enabled else "false",
        "SERMON_AUTH_DISABLED": "false",
    })
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=flags,
    )
    deadline = time.time() + 30
    while time.time() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=5)
            raise RuntimeError(f"isolated server exited early: {stdout[-500:]} {stderr[-500:]}")
        status, _ = _request(f"http://127.0.0.1:{port}/api/runtime")
        if status == 200:
            return process
        time.sleep(0.2)
    process.terminate()
    process.wait(timeout=10)
    raise RuntimeError("isolated server did not become ready")


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _login(base: str, *, register: bool) -> urllib.request.OpenerDirector:
    credentials = {"username": "canary-admin", "password": "canary-password-2026"}
    if register:
        status, body = _request(base + "/api/auth/register", method="POST", payload=credentials)
        if status != 200 or not body.get("ok"):
            raise RuntimeError(f"isolated account registration failed: {status} {body}")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    status, body = _request(base + "/api/auth/login", method="POST", payload=credentials, opener=opener)
    if status != 200 or not body.get("ok") or not list(jar):
        raise RuntimeError(f"isolated login failed: {status} {body}")
    return opener


def smoke() -> dict:
    with tempfile.TemporaryDirectory(prefix="sermon-research-http-") as directory:
        root = Path(directory)
        os.environ["SERMON_USER_ROOT"] = str(root)
        os.environ["RESEARCH_SECTION_CANARY"] = "false"
        from app.core import add_passage, init_db, save_sermon
        from app.migrations import apply_research_sections_migration
        from app.repositories.settings import DB_PATH

        init_db(DB_PATH)
        add_passage("TEST", "ko", "테스트 1:1", "등록된 중심 본문입니다.", "test-only", DB_PATH)
        project = save_sermon("HTTP Canary", "테스트 설교", {"main_reference": "테스트 1:1"}, db_path=DB_PATH)
        apply_research_sections_migration(DB_PATH)

        port = _free_port()
        base = f"http://127.0.0.1:{port}"
        path = f"/api/projects/{project['sermon_id']}/research/sections/structure"
        payload = {
            "context": {"reference": "테스트 1:1"},
            "evidence": {"source_ids": ["TEST:테스트 1:1"], "citation_coverage": 1.0},
            "source_snapshot_id": "isolated-http-smoke",
            "target_project_id": project["sermon_id"],
            "target_reference": "테스트 1:1",
            "confirmation": "ENABLE-STRUCTURE-CANARY",
        }
        results: dict[str, object] = {}

        disabled_server = _start(root, port, False)
        try:
            status, body = _request(base + path)
            results["unauthenticated"] = {"status": status, "code": body.get("code")}
            opener = _login(base, register=True)
            status, body = _request(base + path + "/generate", method="POST", payload=payload, opener=opener)
            results["disabled"] = {"status": status, "code": (body.get("detail") or {}).get("code")}
        finally:
            _stop(disabled_server)

        enabled_server = _start(root, port, True)
        try:
            opener = _login(base, register=False)
            status, plan = _request(base + path + "/dry-run", method="POST", payload=payload, opener=opener)
            results["dry_run"] = {"status": status, "confirmation_required": plan.get("confirmation_required")}
            status, approval = _request(base + path + "/approval-check", method="POST", payload=payload, opener=opener)
            results["approval_check"] = {"status": status, "passed": approval.get("approval_check_passed"), "writes_performed": approval.get("writes_performed")}
            status, generated = _request(base + path + "/generate", method="POST", payload=payload, opener=opener)
            results["generated"] = {"status": status, "ok": generated.get("ok"), "version": (generated.get("section") or {}).get("version")}
            status, retried = _request(base + path + "/retry", method="POST", payload=payload, opener=opener)
            results["retried"] = {"status": status, "ok": retried.get("ok"), "version": (retried.get("section") or {}).get("version")}
            status, versions = _request(base + path + "/versions", opener=opener)
            results["versions"] = {"status": status, "versions": [item["version"] for item in versions.get("items", [])]}
            missing = dict(payload)
            missing["context"] = {"reference": "없는책 1:1"}
            missing["target_reference"] = "없는책 1:1"
            status, blocked = _request(base + path + "/generate", method="POST", payload=missing, opener=opener)
            results["missing_passage"] = {
                "status": status,
                "ok": blocked.get("ok"),
                "section_status": (blocked.get("section") or {}).get("status"),
                "code": ((blocked.get("section") or {}).get("content") or {}).get("code"),
            }
        finally:
            _stop(enabled_server)

        results["ok"] = bool(
            results["unauthenticated"] == {"status": 401, "code": "auth_required"}
            and results["disabled"] == {"status": 503, "code": "research_canary_disabled"}
            and results["dry_run"] == {"status": 200, "confirmation_required": True}
            and results["approval_check"] == {"status": 200, "passed": True, "writes_performed": False}
            and results["generated"] == {"status": 200, "ok": True, "version": 1}
            and results["retried"] == {"status": 200, "ok": True, "version": 2}
            and results["versions"] == {"status": 200, "versions": [2, 1]}
            and results["missing_passage"] == {
                "status": 200,
                "ok": False,
                "section_status": "insufficient_evidence",
                "code": "research_insufficient_evidence",
            }
        )
        return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    result = smoke()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
