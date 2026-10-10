import sqlite3

import pytest

from app.migrations import apply_research_sections_migration
from app.repositories.research_sections import ResearchSectionRepository


def _repository(tmp_path):
    db = tmp_path / "bible.db"
    with sqlite3.connect(db) as con:
        con.execute(
            "CREATE TABLE sermons (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        con.execute("INSERT INTO sermons(topic, created_at) VALUES('테스트', datetime('now'))")
    apply_research_sections_migration(db)
    return db, ResearchSectionRepository(db)


def test_repository_creates_new_versions_without_overwriting_prior_content(tmp_path):
    _, repository = _repository(tmp_path)

    first = repository.create_version(
        project_id=1,
        section_type="structure",
        status="ready",
        content={"title": "첫 구조"},
        source_coverage=1.0,
        quality_status="passed",
        source_snapshot_id="source-1",
    )
    second = repository.create_version(
        project_id=1,
        section_type="structure",
        status="ready",
        content={"title": "재생성 구조"},
        source_coverage=1.0,
        quality_status="passed",
        source_snapshot_id="source-2",
    )

    assert (first["version"], second["version"]) == (1, 2)
    assert repository.latest(1, "structure")["content"] == {"title": "재생성 구조"}
    versions = repository.list_versions(1, "structure")
    assert [item["version"] for item in versions] == [2, 1]
    assert versions[1]["content"] == {"title": "첫 구조"}


def test_repository_rejects_invalid_state_and_missing_project(tmp_path):
    _, repository = _repository(tmp_path)

    with pytest.raises(ValueError, match="ready section requires content"):
        repository.create_version(
            project_id=1, section_type="structure", status="ready", content={}
        )
    with pytest.raises(sqlite3.IntegrityError):
        repository.create_version(
            project_id=999, section_type="structure", status="ready", content={"title": "없음"}
        )


def test_repository_requires_explicit_migration(tmp_path):
    db = tmp_path / "bible.db"
    with pytest.raises(RuntimeError, match="migration is required"):
        ResearchSectionRepository(db).list_versions(1, "structure")


def test_repository_readiness_check_is_read_only(tmp_path):
    db, repository = _repository(tmp_path)
    before = db.stat().st_mtime_ns
    repository.require_ready()
    assert db.stat().st_mtime_ns == before
