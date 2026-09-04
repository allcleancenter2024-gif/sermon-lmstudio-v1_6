from pathlib import Path

import app.main as main
import launcher
import verify_version
from app.routers.projects import workflow_config
from app.version import APP_VERSION, app_version_major, read_app_version


ROOT = Path(__file__).resolve().parents[1]


def test_version_file_is_runtime_source_of_truth():
    assert APP_VERSION == read_app_version()
    assert APP_VERSION == (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    assert main.APP_VERSION == APP_VERSION
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
