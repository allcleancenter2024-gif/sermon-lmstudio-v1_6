from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app.main as main
import launcher
import verify_version
from app.routers import health
from app.routers.projects import workflow_config
from app.version import APP_VERSION, app_version_major, read_app_version


ROOT = Path(__file__).resolve().parents[1]


def test_version_file_is_runtime_source_of_truth():
    assert APP_VERSION == read_app_version()
    assert APP_VERSION == (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    assert main.APP_VERSION == APP_VERSION
    assert health.APP_VERSION == APP_VERSION
    assert launcher.APP_VERSION == APP_VERSION
    assert verify_version.APP_VERSION == APP_VERSION


def test_legacy_workflow_version_remains_compatible():
    config = workflow_config()
    assert config["app_version"] == APP_VERSION
    assert config["version"] == app_version_major()


def test_start_script_reads_version_file():
    script = (ROOT / "start.bat").read_text(encoding="utf-8")
    assert 'VERSION.txt' in script
    assert 'set "EXPECTED_VERSION=40.9.10"' not in script
    assert "Extract the V%EXPECTED_VERSION% package" in script


def test_home_replaces_only_the_validated_version_marker():
    with patch("app.main.session_user", return_value={"username": "admin"}):
        html = main.home(SimpleNamespace(cookies={}))
    assert "__APP_VERSION__" not in html
    assert f"V{APP_VERSION}" in html
    assert f"/static/app.js?v={APP_VERSION}" in html
