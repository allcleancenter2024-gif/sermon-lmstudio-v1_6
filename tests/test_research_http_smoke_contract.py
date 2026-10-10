from pathlib import Path


def test_isolated_http_smoke_script_preserves_localhost_auth_and_canary_contracts():
    source = (Path(__file__).resolve().parents[1] / "scripts" / "smoke_research_http.py").read_text(encoding="utf-8")
    assert '"--host", "127.0.0.1"' in source
    assert '"SERMON_AUTH_DISABLED": "false"' in source
    assert '"RESEARCH_SECTION_CANARY": "true" if enabled else "false"' in source
    assert 'TemporaryDirectory(prefix="sermon-research-http-")' in source
    assert 'results["unauthenticated"] == {"status": 401, "code": "auth_required"}' in source
    assert '"code": "research_insufficient_evidence"' in source
    assert '"confirmation": "ENABLE-STRUCTURE-CANARY"' in source
    assert '"/dry-run"' in source
    assert '"/approval-check"' in source
