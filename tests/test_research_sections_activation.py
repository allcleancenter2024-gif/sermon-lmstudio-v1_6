import sqlite3
from contextlib import closing

import pytest

from app.core import init_db
from scripts.activate_research_sections import activate


def test_activation_creates_valid_backup_and_applies_once(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_SECTION_CANARY", "false")
    db, backups = tmp_path / "data" / "bible.db", tmp_path / "backups"
    init_db(db)
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO sermons(topic, created_at) VALUES('보존', datetime('now'))")

    result = activate(db, backups, "40.9.13")
    second = activate(db, backups, "40.9.13")

    assert result["ok"] is True and result["already_applied"] is False
    assert result["backup_inspection"]["ok"] is True
    assert result["before"]["counts"] == result["after"]["counts"]
    assert result["after"]["quick_check"] == "ok"
    assert second["already_applied"] is True
    assert len(list(backups.glob("sermon_backup_*.zip"))) == 1


def test_activation_auto_restores_backup_after_failed_migration(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_SECTION_CANARY", "false")
    db, backups = tmp_path / "data" / "bible.db", tmp_path / "backups"
    init_db(db)

    def broken_migration(path):
        with closing(sqlite3.connect(path)) as con, con:
            con.execute("CREATE TABLE sermon_sections(id INTEGER PRIMARY KEY)")
        raise RuntimeError("simulated migration failure")

    with pytest.raises(RuntimeError, match="simulated migration failure"):
        activate(db, backups, "40.9.13", apply_migration=broken_migration)

    with sqlite3.connect(db) as con:
        assert con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sermon_sections'"
        ).fetchone() is None
        assert con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert len(list(backups.glob("sermon_backup_*.zip"))) == 2


def test_activation_refuses_when_canary_is_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_SECTION_CANARY", "true")
    db = tmp_path / "bible.db"
    init_db(db)
    with pytest.raises(RuntimeError, match="OFF"):
        activate(db, tmp_path / "backups", "40.9.13")
    assert not (tmp_path / "backups").exists()
