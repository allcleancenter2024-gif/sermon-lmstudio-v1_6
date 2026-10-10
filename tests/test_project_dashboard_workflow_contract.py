from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_dashboard_workflow_call_graph_contract_is_present():
    repository = (ROOT / "app" / "repositories" / "project.py").read_text(encoding="utf-8")
    core = (ROOT / "app" / "core.py").read_text(encoding="utf-8")
    presenter = (ROOT / "app" / "services" / "project_dashboard_presenter.py").read_text(encoding="utf-8")
    service = (ROOT / "app" / "services" / "project_workflow_service.py").read_text(encoding="utf-8")
    facade = (ROOT / "app" / "application" / "project_facade.py").read_text(encoding="utf-8")
    router = (ROOT / "app" / "routers" / "projects.py").read_text(encoding="utf-8")

    assert "def fetch_project_dashboard_inputs(" in repository
    assert "class ProjectDashboardInput(TypedDict):" in repository
    assert "-> list[ProjectDashboardInput]" in repository
    assert "fetch_project_dashboard_inputs(db_path)" in core
    assert "from app.services.project_dashboard_presenter import compose_project_dashboard" in core
    assert "load_review_state=sermon_review_state" in core
    assert "estimate_minutes=estimate_minutes" in core
    assert "def compose_project_dashboard(" in presenter
    assert "from app.core" not in presenter
    assert "from fastapi" not in presenter
    assert "from app.repositories.project import" in facade
    assert "from app.services.project_dashboard_presenter import compose_project_dashboard" in facade
    assert "from app.services.project_workflow_service import build_workflow_status" in facade
    assert "fetch_project_dashboard_inputs(db_path)" in facade
    assert "load_versions=sermon_versions" in facade
    assert "load_review_state=sermon_review_state" in facade
    assert "def build_workflow_status(" in service
    assert "def project_dashboard(" in core
    assert "def sermon_workflow_status(" in core
    assert "def dashboard(" in facade
    assert "def workflow(sermon_id: int, version: int," in facade
    assert "from app.application.project_facade import" in router


def test_project_dashboard_and_workflow_external_contracts_remain_fixed():
    router = (ROOT / "app" / "routers" / "projects.py").read_text(encoding="utf-8")
    presenter = (ROOT / "app" / "services" / "project_dashboard_presenter.py").read_text(encoding="utf-8")
    service = (ROOT / "app" / "services" / "project_workflow_service.py").read_text(encoding="utf-8")

    assert '@router.get("/api/projects/dashboard")' in router
    assert '@router.get("/api/sermons/{sermon_id}/versions/{version}/workflow")' in router
    assert '"projects": projects' in presenter
    assert '"summary": {"total": len(projects)' in presenter
    assert '"steps": steps' in service
    assert '"completed": sum(1 for x in steps if x["status"] == "completed")' in service
    assert '"next_step": next_step' in service
    assert '"locked": locked_ok' in service


def test_workflow_step_keys_are_fixed_for_ui_compatibility():
    service = (ROOT / "app" / "services" / "project_workflow_service.py").read_text(encoding="utf-8")

    for key in ("brief", "bible", "languages", "draft", "evidence", "review", "final"):
        assert f'step("{key}"' in service


def test_workflow_calculation_isolated_behind_core_compatibility_wrapper():
    core = (ROOT / "app" / "core.py").read_text(encoding="utf-8")
    service = (ROOT / "app" / "services" / "project_workflow_service.py").read_text(encoding="utf-8")

    assert 'from app.services.project_workflow_service import build_workflow_status' in core
    assert 'load_versions=sermon_versions' in core
    assert 'load_review_state=sermon_review_state' in core
    assert 'def build_workflow_status(' in service
    assert 'from app.core' not in service
    assert 'from fastapi' not in service


def test_dashboard_presenter_composes_contract_without_database():
    from app.services.project_dashboard_presenter import compose_project_dashboard

    result = compose_project_dashboard(
        [{
            "sermon": {"id": 7, "topic": "은혜", "created_at": "2026-09-30T12:00:00"},
            "version": 2,
            "version_item": {
                "content": "설교 본문",
                "metadata": {"reading_cpm": 300, "target_minutes": 25},
                "created_at": "2026-09-30T12:30:00",
            },
            "project": {"service_date": "2026-10-01", "series_name": "시리즈", "preacher": "설교자", "notes": "메모"},
        }],
        ROOT / "test.db",
        load_review_state=lambda sermon_id, version, db_path: {
            "state": "approved", "locked": False, "audit": {"status": "passed"}
        },
        estimate_minutes=lambda content, chars_per_minute: 4.5,
        reading_cpm=330,
    )

    assert result["reading_cpm"] == 330
    assert result["summary"] == {
        "total": 1, "unreviewed": 0, "comment": 0, "changes_requested": 0, "approved": 1, "locked": 0,
    }
    assert result["projects"][0] == {
        "sermon_id": 7, "topic": "은혜", "latest_version": 2,
        "service_date": "2026-10-01", "series_name": "시리즈", "preacher": "설교자", "notes": "메모",
        "state": "approved", "audit_status": "passed", "locked": False, "target_minutes": 25,
        "minutes_estimate": 4.5, "reading_cpm": 300, "updated_at": "2026-09-30T12:30:00",
    }


def test_rag_storage_helper_isolated_behind_core_compatibility_wrapper():
    core = (ROOT / "app" / "core.py").read_text(encoding="utf-8")
    storage = (ROOT / "app" / "rag" / "storage.py").read_text(encoding="utf-8")

    assert "from app.rag.storage import pack_rag_vector as pack_rag_vector_storage" in core
    assert 'return pack_rag_vector_storage(vector)' in core
    assert "def pack_rag_vector(vector)" in storage
    assert "from app.core" not in storage
    assert "from fastapi" not in storage


def test_rag_storage_helper_preserves_vector_dimension_and_norm():
    from app.rag.storage import pack_rag_vector

    packed, dimension, norm = pack_rag_vector([3, 4])

    assert len(packed) == 2 * 4
    assert dimension == 2
    assert norm == 5.0


def test_reading_metrics_isolated_behind_core_compatibility_wrapper():
    core = (ROOT / "app" / "core.py").read_text(encoding="utf-8")
    metrics = (ROOT / "app" / "services" / "reading_metrics.py").read_text(encoding="utf-8")

    assert "from app.services.reading_metrics import estimate_minutes as estimate_minutes_service" in core
    assert "return estimate_minutes_service(text, chars_per_minute)" in core
    assert "def estimate_minutes(" in metrics
    assert "from app.core" not in metrics
    assert "from fastapi" not in metrics


def test_reading_metrics_preserves_non_whitespace_duration_calculation():
    from app.services.reading_metrics import estimate_minutes

    assert estimate_minutes("가 나\n다", 3) == 1.0
    assert estimate_minutes("가" * 660) == 2.0
