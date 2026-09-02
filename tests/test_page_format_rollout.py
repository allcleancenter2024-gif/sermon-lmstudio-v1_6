from __future__ import annotations

import json

from app.formatting.registry import PRESETS, THEMES, TEMPLATES, compatibility_matrix, select_output
from app.formatting.rollout import v2_is_selected
from app.formatting.telemetry import record_event


def test_registry_and_smart_defaults():
    selection = select_output(document_type="sermon", format="html", preset="web-standard")
    assert selection["profile"] == "sermon"
    assert selection["theme"] == "default"
    assert selection["template"].status == "stable"
    assert select_output(document_type="unknown", format="html")["profile"] == "generic"
    assert set({"default", "pastel", "high-contrast", "print", "compact"}) <= set(THEMES)
    assert "web-dashboard" in PRESETS and "sermon.standard" in TEMPLATES


def test_incompatible_override_is_safe_fallback():
    result = select_output(document_type="dashboard", format="docx", theme="print")
    assert result["profile"] == "generic"
    assert result["warnings"]
    assert "docx" in compatibility_matrix()["sermon"]


def test_preset_cannot_change_endpoint_format_unsafely():
    result = select_output(document_type="sermon", format="html", preset="print-a4")
    assert result["format"] == "html"
    assert result["preset"] is None
    assert result["warnings"]


def test_rollout_is_deterministic_and_supports_canary():
    assert v2_is_selected("abc", "internal") is True
    assert v2_is_selected("abc", "legacy") is False
    assert v2_is_selected("abc", "50") == v2_is_selected("abc", "50")


def test_legacy_and_v2_rollout_paths_are_both_available(monkeypatch):
    monkeypatch.setenv("PAGE_FORMAT_ROLLOUT", "legacy")
    assert v2_is_selected("rollback-check") is False
    monkeypatch.setenv("PAGE_FORMAT_ROLLOUT", "100")
    assert v2_is_selected("rollback-check") is True


def test_telemetry_contains_no_content(tmp_path, monkeypatch):
    monkeypatch.setattr("app.formatting.telemetry.USER_ROOT", tmp_path)
    event = record_event("render_completed", format="html", profile="sermon", quality_score=95)
    row = json.loads((tmp_path / "data" / "page_format_telemetry.jsonl").read_text(encoding="utf-8"))
    assert event["render_id"] and row["event"] == "render_completed"
    assert "본문" not in row and "content" not in row
