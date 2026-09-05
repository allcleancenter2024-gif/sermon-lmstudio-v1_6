from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_architecture_map_groups_added_features_without_replacing_workflow_panels():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert 'id="architecturePanel"' in html
    for label in ("준비", "연구", "근거", "생성", "검토", "출력·운영"):
        assert f"<h3>{label}</h3>" in html
    for panel_id in (
        "firstRunPanel",
        "readinessPanel",
        "researchPanel",
        "languagePanel",
        "requestPanel",
        "outlinePanel",
        "resultPanel",
        "savedPanel",
        "previewPanel",
        "workSummaryPanel",
    ):
        assert f'data-jump="{panel_id}"' in html

    # The map is additive: the existing workflow anchors remain available.
    for panel_id in ("requestPanel", "researchPanel", "outlinePanel", "resultPanel", "savedPanel"):
        assert f'id="{panel_id}"' in html


def test_architecture_map_has_responsive_and_focus_styles():
    css = (ROOT / "static" / "v2.css").read_text(encoding="utf-8")

    assert ".architecture-grid" in css
    assert ".architecture-card button:hover" in css
    assert ".architecture-card button:focus-visible" in css
    assert "@media(max-width:600px)" in css
