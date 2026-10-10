import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_main_registers_feature_gated_research_router_without_auto_migration(tmp_path):
    code = """
import json, sqlite3
from app.main import app, DB_PATH
paths = sorted(path for path in app.openapi()['paths'] if '/research/sections/' in path)
with sqlite3.connect(DB_PATH) as con:
    migrated = bool(con.execute(\"SELECT 1 FROM sqlite_master WHERE type='table' AND name='sermon_sections'\").fetchone())
print(json.dumps({'paths': paths, 'migrated': migrated}))
"""
    env = dict(os.environ)
    env["SERMON_USER_ROOT"] = str(tmp_path)
    env["RESEARCH_SECTION_CANARY"] = "false"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(completed.stdout.strip().splitlines()[-1])

    assert result["migrated"] is False
    assert result["paths"] == [
        "/api/projects/{project_id}/research/sections/{section_id}",
        "/api/projects/{project_id}/research/sections/{section_id}/approval-check",
        "/api/projects/{project_id}/research/sections/{section_id}/dry-run",
        "/api/projects/{project_id}/research/sections/{section_id}/generate",
        "/api/projects/{project_id}/research/sections/{section_id}/retry",
        "/api/projects/{project_id}/research/sections/{section_id}/versions",
    ]


def test_main_research_routes_remain_behind_existing_auth_middleware():
    source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "app.include_router(build_research_router(" in source
    assert 'request.url.path.startswith("/api/projects/")' not in source
    assert 'status_code=401' in source
    assert '"code": "auth_required"' in source
    assert "auth_db=AUTH_DB" in source
