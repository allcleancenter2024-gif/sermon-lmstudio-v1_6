from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_no_login_launcher_sets_auth_disabled_before_import():
    source = (ROOT / "New_launcher.py").read_text(encoding="utf-8")
    assert 'os.environ["SERMON_AUTH_DISABLED"] = "1"' in source
    assert source.index('os.environ["SERMON_AUTH_DISABLED"] = "1"') < source.index("from launcher import main")


def test_main_has_separate_no_login_gate_and_keeps_login_variant():
    source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert 'AUTH_DISABLED = os.getenv("SERMON_AUTH_DISABLED"' in source
    assert "if not AUTH_DISABLED and not public" in source
    assert "if not AUTH_DISABLED and session_user" in source
    assert "app.include_router(build_auth_router(AUTH_DB))" in source
