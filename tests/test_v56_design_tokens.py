from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_design_tokens_are_loaded_before_v2_overrides():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    tokens = (ROOT / "static" / "tokens.css").read_text(encoding="utf-8")
    v2 = (ROOT / "static" / "v2.css").read_text(encoding="utf-8")

    assert 'href="/static/tokens.css?v=__APP_VERSION__"' in html
    assert html.index("/static/tokens.css") < html.index("/static/v2.css")
    for token in ("--color-primary", "--color-action", "--color-success", "--color-danger", "--radius-md", "--space-4"):
        assert token in tokens
    assert "var(--color-success)" in v2


def test_design_tokens_preserve_accessibility_states_and_responsive_map():
    tokens = (ROOT / "static" / "tokens.css").read_text(encoding="utf-8")
    v2 = (ROOT / "static" / "v2.css").read_text(encoding="utf-8")

    assert ":focus-visible" in tokens
    assert "prefers-reduced-motion" in tokens
    assert "@media(max-width:600px)" in v2
    assert "@media(max-width:900px)" in v2
