import sqlite3

import pytest

from app.core import init_db
from scripts.rehearse_research_canary_activation import rehearse_activation


def test_rehearsal_uses_disposable_clone_and_never_activates_source(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_SECTION_CANARY", "false")
    database = tmp_path / "bible.db"
    init_db(database)
    result = rehearse_activation(database)
    assert result["ok"] is True
    assert result["activation_performed"] is False
    assert result["source_unchanged"] is True
    with sqlite3.connect(database) as con:
        assert con.execute("SELECT 1 FROM sqlite_master WHERE name='sermon_sections'").fetchone() is None


def test_rehearsal_validates_already_applied_schema_without_writing(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_SECTION_CANARY", "false")
    database = tmp_path / "bible.db"
    init_db(database)
    from app.migrations import apply_research_sections_migration
    apply_research_sections_migration(database)
    result = rehearse_activation(database)
    assert result["ok"] is True
    assert result["mode"] == "schema_already_activated"
    assert result["activation_performed"] is False


def test_rehearsal_refuses_enabled_feature_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_SECTION_CANARY", "true")
    database = tmp_path / "bible.db"
    init_db(database)
    with pytest.raises(RuntimeError, match="OFF"):
        rehearse_activation(database)
