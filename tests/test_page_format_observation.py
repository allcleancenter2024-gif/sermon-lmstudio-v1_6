from __future__ import annotations

import json

import pytest

from app.formatting.fallback import with_legacy_fallback
from app.formatting.telemetry import summarize_events


def test_fallback_records_reason_without_content(tmp_path, monkeypatch):
    monkeypatch.setattr("app.formatting.telemetry.USER_ROOT", tmp_path)
    result = with_legacy_fallback(format="html", profile="sermon", theme="default", preset=None, render_v2=lambda: (_ for _ in ()).throw(RuntimeError("renderer")), render_legacy=lambda: "legacy")
    assert result == "legacy"
    row = json.loads((tmp_path / "data" / "page_format_telemetry.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert row["event"] == "fallback_used"
    assert row["error_code"] == "PF_FALLBACK_HTML_RENDER"
    assert "legacy" not in row


def test_validation_error_never_silently_falls_back():
    with pytest.raises(ValueError):
        with_legacy_fallback(format="html", profile="sermon", theme="default", preset=None, render_v2=lambda: (_ for _ in ()).throw(ValueError("invalid")), render_legacy=lambda: "must not run")


def test_observation_summary_is_technical_only(tmp_path):
    path = tmp_path / "events.jsonl"
    rows = [
        {"event": "render_completed", "format": "html", "duration_ms": 10, "quality_score": 95},
        {"event": "render_completed", "format": "pdf", "duration_ms": 30, "quality_score": 90},
        {"event": "fallback_used", "format": "pdf", "status": "fallback"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    summary = summarize_events(path)
    assert summary["render_count"] == 2
    assert summary["fallback_rate"] == 0.5
    assert summary["p50_render_ms"] == 10
    assert "content" not in summary
