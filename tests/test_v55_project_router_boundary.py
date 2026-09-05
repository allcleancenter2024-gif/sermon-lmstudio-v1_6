from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_summary_route_is_owned_by_project_router():
    projects = (ROOT / "app" / "routers" / "projects.py").read_text(encoding="utf-8")
    main = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert '@router.get("/api/project-summary")' in projects
    assert '@app.get("/api/project-summary")' not in main
    assert "build_project_summary(RESOURCE_ROOT, APP_VERSION)" in projects


def test_project_summary_compatibility_contract_remains_documented_in_app():
    projects = (ROOT / "app" / "routers" / "projects.py").read_text(encoding="utf-8")

    assert "from app.project_summary import build_project_summary" in projects
    assert "from app.version import APP_VERSION" in projects
