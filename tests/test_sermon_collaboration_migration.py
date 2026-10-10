import sqlite3

import pytest

from app.migrations import (
    SERMON_COLLABORATION_MIGRATION_ID,
    apply_sermon_collaboration_migration,
    rollback_sermon_collaboration_migration,
)
from app.repositories.collaboration import SermonCollaborationRepository


def _legacy_db(path):
    with sqlite3.connect(path) as con:
        con.execute(
            "CREATE TABLE sermons (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        con.execute("CREATE TABLE legacy_guard (value TEXT NOT NULL)")
        con.execute("INSERT INTO legacy_guard(value) VALUES('preserve-me')")
        con.execute("INSERT INTO sermons(topic, created_at) VALUES('legacy sermon', '2026-10-08')")


def test_collaboration_migration_is_idempotent_and_does_not_guess_legacy_owners(tmp_path):
    db = tmp_path / "bible.db"
    _legacy_db(db)

    first = apply_sermon_collaboration_migration(db)
    second = apply_sermon_collaboration_migration(db)

    assert first == {"migration_id": SERMON_COLLABORATION_MIGRATION_ID, "applied": True}
    assert second == {"migration_id": SERMON_COLLABORATION_MIGRATION_ID, "applied": False}
    repository = SermonCollaborationRepository(db)
    assert repository.get_assignment(1) is None
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT value FROM legacy_guard").fetchone()[0] == "preserve-me"
        assert con.execute("SELECT COUNT(*) FROM sermons").fetchone()[0] == 1
        assert con.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_collaboration_repository_assigns_distinct_roles_with_audited_revisions(tmp_path):
    db = tmp_path / "bible.db"
    _legacy_db(db)
    apply_sermon_collaboration_migration(db)
    repository = SermonCollaborationRepository(db)

    first = repository.assign(
        sermon_id=1,
        author_id="author",
        reviewer_id="reviewer",
        approver_id="approver",
        actor_id="admin",
        expected_revision=0,
    )
    second = repository.assign(
        sermon_id=1,
        author_id="author",
        reviewer_id="reviewer-2",
        approver_id="approver",
        actor_id="admin",
        expected_revision=1,
    )

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert repository.get_assignment(1) == second
    assert [event["assignment_revision"] for event in repository.list_assignment_events(1)] == [1, 2]
    assert repository.list_for_user("author")[0]["sermon_id"] == 1
    assert repository.list_for_user("unassigned")==[]


def test_workflow_events_are_bound_to_the_assignment_revision(tmp_path):
    db = tmp_path / "bible.db"
    _legacy_db(db)
    apply_sermon_collaboration_migration(db)
    repository = SermonCollaborationRepository(db)
    repository.assign(
        sermon_id=1, author_id="author", reviewer_id="reviewer", approver_id="approver",
        actor_id="admin", expected_revision=0,
    )
    event = repository.record_workflow_event(
        sermon_id=1, assignment_revision=1, actor_id="reviewer", action="review_status",
        version=1, status="reviewed", review_created_at="2026-10-08T12:00:00",
    )
    assert event["details"]["status"] == "reviewed"
    assert len(repository.list_workflow_events(1, assignment_revision=1, version=1)) == 1
    repository.assign(
        sermon_id=1, author_id="author", reviewer_id="reviewer-2", approver_id="approver",
        actor_id="admin", expected_revision=1,
    )
    assert repository.list_workflow_events(1, assignment_revision=2, version=1) == []
    assert len(repository.list_workflow_events(1, version=1)) == 1
    with pytest.raises(ValueError, match="assignment_revision_mismatch"):
        repository.record_workflow_event(
            sermon_id=1, assignment_revision=1, actor_id="reviewer", action="review_status",
            version=1, status="approved", review_created_at="2026-10-08T12:01:00",
        )


def test_collaboration_repository_rejects_bad_roles_missing_sermons_and_stale_revision(tmp_path):
    db = tmp_path / "bible.db"
    _legacy_db(db)
    apply_sermon_collaboration_migration(db)
    repository = SermonCollaborationRepository(db)

    with pytest.raises(ValueError, match="different accounts"):
        repository.assign(
            sermon_id=1, author_id="same", reviewer_id="same", approver_id="approver",
            actor_id="admin", expected_revision=0,
        )
    with pytest.raises(ValueError, match="expected_revision_mismatch"):
        repository.assign(
            sermon_id=1, author_id="author", reviewer_id="reviewer", approver_id="approver",
            actor_id="admin", expected_revision=1,
        )
    with pytest.raises(ValueError, match="프로젝트를 찾을 수 없습니다"):
        repository.assign(
            sermon_id=99, author_id="author", reviewer_id="reviewer", approver_id="approver",
            actor_id="admin", expected_revision=0,
        )
    assert repository.get_assignment(1) is None
    assert repository.list_assignment_events(1) == []


def test_collaboration_migration_can_roll_back_only_before_assignment_data_exists(tmp_path):
    db = tmp_path / "bible.db"
    _legacy_db(db)
    apply_sermon_collaboration_migration(db)

    assert rollback_sermon_collaboration_migration(db)["rolled_back"] is True
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT value FROM legacy_guard").fetchone()[0] == "preserve-me"
        assert con.execute("SELECT COUNT(*) FROM sermons").fetchone()[0] == 1
        assert con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sermon_collaboration_assignments'"
        ).fetchone() is None


@pytest.mark.parametrize("table", ["sermon_collaboration_assignments", "sermon_collaboration_events"])
def test_collaboration_rollback_refuses_when_any_assignment_history_exists(tmp_path, table):
    db = tmp_path / "bible.db"
    _legacy_db(db)
    apply_sermon_collaboration_migration(db)
    repository = SermonCollaborationRepository(db)
    assignment = repository.assign(
        sermon_id=1, author_id="author", reviewer_id="reviewer", approver_id="approver",
        actor_id="admin", expected_revision=0,
    )
    if table == "sermon_collaboration_assignments":
        with sqlite3.connect(db) as con:
            con.execute("DELETE FROM sermon_collaboration_events")

    with pytest.raises(RuntimeError, match="DB 백업 복원"):
        rollback_sermon_collaboration_migration(db)
    assert assignment["revision"] == 1
