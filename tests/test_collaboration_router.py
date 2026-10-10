from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import create_session, create_user
from app.migrations import apply_sermon_collaboration_migration
from app.repositories.collaboration import SermonCollaborationRepository
from app.routers.collaboration import AssignmentRequest, build_collaboration_router


class FakeRepository:
    def __init__(self, *, error=None):
        self.error = error
        self.assignments = []

    def list_for_user(self, user_id):
        if self.error:
            raise self.error
        return [{"author_id": user_id}]

    def get_assignment(self, sermon_id):
        if self.error:
            raise self.error
        return None

    def assign(self, **kwargs):
        if self.error:
            raise self.error
        self.assignments.append(kwargs)
        return kwargs


def _endpoint(router, path, method):
    return next(route.endpoint for route in router.routes if route.path == path and method in route.methods)


def _request(username=None):
    token = create_session(username) if username else None
    return SimpleNamespace(cookies={"sermon_session": token} if token else {})


def _auth_db(tmp_path):
    db = tmp_path / "auth.sqlite3"
    assert create_user(db, "admin", "admin-password-123")
    assert create_user(db, "writer", "writer-password-123")
    assert create_user(db, "reviewer", "reviewer-password-123")
    assert create_user(db, "approver", "approver-password-123")
    return db


def test_collaboration_assignment_requires_authenticated_admin_and_real_accounts(tmp_path):
    repository = FakeRepository()
    router = build_collaboration_router(repository=repository, auth_db=_auth_db(tmp_path))
    assign = _endpoint(router, "/api/collaboration/sermons/{sermon_id}/assignment", "PUT")
    data = AssignmentRequest(author_id="writer", reviewer_id="reviewer", approver_id="approver", expected_revision=0)

    with pytest.raises(HTTPException) as unauthenticated:
        assign(5, data, _request())
    assert unauthenticated.value.status_code == 401

    with pytest.raises(HTTPException) as forbidden:
        assign(5, data, _request("writer"))
    assert forbidden.value.status_code == 403

    result = assign(5, data, _request("admin"))
    assert result["ok"] is True
    assert repository.assignments[0]["actor_id"] == "admin"


def test_account_roster_is_admin_only(tmp_path):
    router = build_collaboration_router(repository=FakeRepository(), auth_db=_auth_db(tmp_path))
    users = _endpoint(router, "/api/collaboration/users", "GET")

    with pytest.raises(HTTPException) as forbidden:
        users(_request("writer"))
    assert forbidden.value.status_code == 403
    assert {item["username"] for item in users(_request("admin"))["items"]} == {"admin", "writer", "reviewer", "approver"}


def test_collaboration_api_never_persists_when_schema_is_not_migrated(tmp_path):
    repository = FakeRepository(error=RuntimeError("sermon collaboration migration is required"))
    router = build_collaboration_router(repository=repository, auth_db=_auth_db(tmp_path))
    endpoint = _endpoint(router, "/api/collaboration/assignments", "GET")

    with pytest.raises(HTTPException) as error:
        endpoint(_request("writer"))

    assert error.value.status_code == 503
    assert error.value.detail["code"] == "collaboration_schema_unavailable"


def test_collaboration_api_is_unavailable_when_authentication_is_disabled(tmp_path):
    router = build_collaboration_router(repository=FakeRepository(), auth_db=_auth_db(tmp_path), auth_enabled=False)
    endpoint = _endpoint(router, "/api/collaboration/assignments", "GET")

    with pytest.raises(HTTPException) as error:
        endpoint(_request("admin"))

    assert error.value.status_code == 503


def test_admin_assignment_round_trips_through_sqlite_and_user_scope(tmp_path):
    sermon_db = tmp_path / "sermons.sqlite3"
    import sqlite3
    with sqlite3.connect(sermon_db) as connection:
        connection.execute("CREATE TABLE sermons (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO sermons(id) VALUES (5)")
    apply_sermon_collaboration_migration(sermon_db)
    repository = SermonCollaborationRepository(sermon_db)
    router = build_collaboration_router(repository=repository, auth_db=_auth_db(tmp_path))
    assign = _endpoint(router, "/api/collaboration/sermons/{sermon_id}/assignment", "PUT")
    mine = _endpoint(router, "/api/collaboration/assignments", "GET")

    assigned = assign(
        5,
        AssignmentRequest(author_id="writer", reviewer_id="reviewer", approver_id="approver", expected_revision=0),
        _request("admin"),
    )
    writer_assignments = mine(_request("writer"))

    assert assigned["assignment"]["revision"] == 1
    assert writer_assignments["items"][0]["sermon_id"] == 5
    assert repository.list_assignment_events(5)[0]["actor_id"] == "admin"
