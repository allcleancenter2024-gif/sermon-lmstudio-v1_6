from app.application.reference_catalog import ReferenceCatalog, ReferenceSource
from app.application.reference_ui_contract import build_reference_dashboard


def test_reference_dashboard_is_read_only_and_apply_is_disabled():
    source = ReferenceSource("source-1", "Example", "research", "https://example.test/")
    dashboard = build_reference_dashboard(ReferenceCatalog((source,), ("example.test",)))

    assert dashboard["menu"]["label"] == "[관련자료참고]"
    assert dashboard["catalog_valid"] is True
    assert dashboard["applyable_source_ids"] == []
    assert dashboard["apply_action"]["enabled"] is False


def test_invalid_catalog_is_exposed_as_status_without_raising():
    source = ReferenceSource("bad", "Bad", "research", "javascript:alert(1)")
    dashboard = build_reference_dashboard(ReferenceCatalog((source,)))

    assert dashboard["catalog_valid"] is False
    assert dashboard["catalog_errors"]
    assert dashboard["apply_action"]["enabled"] is False
