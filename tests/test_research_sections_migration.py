import sqlite3

import pytest

from app.migrations import (
    RESEARCH_SECTIONS_MIGRATION_ID,
    apply_research_sections_migration,
    rollback_research_sections_migration,
)


def _legacy_db(path):
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE sermons (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        con.execute("CREATE TABLE legacy_guard (value TEXT NOT NULL)")
        con.execute("INSERT INTO legacy_guard(value) VALUES('preserve-me')")


def test_research_sections_migration_is_idempotent_and_preserves_legacy_tables(tmp_path):
    db = tmp_path / "bible.db"
    _legacy_db(db)

    first = apply_research_sections_migration(db)
    second = apply_research_sections_migration(db)

    assert first == {"migration_id": RESEARCH_SECTIONS_MIGRATION_ID, "applied": True}
    assert second == {"migration_id": RESEARCH_SECTIONS_MIGRATION_ID, "applied": False}
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT value FROM legacy_guard").fetchone()[0] == "preserve-me"
        columns = {row[1] for row in con.execute("PRAGMA table_info(sermon_sections)")}
        assert {"project_id", "section_type", "version", "content_json", "source_snapshot_id"} <= columns


def test_empty_research_sections_migration_can_round_trip(tmp_path):
    db = tmp_path / "bible.db"
    _legacy_db(db)
    apply_research_sections_migration(db)

    assert rollback_research_sections_migration(db)["rolled_back"] is True
    with sqlite3.connect(db) as con:
        assert con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sermon_sections'"
        ).fetchone() is None
        assert con.execute("SELECT value FROM legacy_guard").fetchone()[0] == "preserve-me"
    assert apply_research_sections_migration(db)["applied"] is True


def test_research_sections_rollback_refuses_user_data(tmp_path):
    db = tmp_path / "bible.db"
    _legacy_db(db)
    apply_research_sections_migration(db)
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO sermons(topic, created_at) VALUES('테스트', datetime('now'))")
        con.execute(
            """INSERT INTO sermon_sections(
                   project_id, section_type, version, status, content_json, created_at, updated_at
               ) VALUES(1, 'structure', 1, 'ready', '{}', datetime('now'), datetime('now'))"""
        )

    with pytest.raises(RuntimeError, match="백업 복원"):
        rollback_research_sections_migration(db)
