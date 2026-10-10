from pathlib import Path


def test_reference_panel_is_read_only_and_has_disabled_apply_action():
    html = (Path(__file__).parents[1] / "templates" / "index.html").read_text(encoding="utf-8")

    assert 'data-jump="referenceSourcesPanel"' in html
    assert 'id="referenceSourcesPanel"' in html
    assert "[관련자료참고]" in html
    assert 'disabled aria-disabled="true"' in html
    assert "[관련내용 적용]" in html
