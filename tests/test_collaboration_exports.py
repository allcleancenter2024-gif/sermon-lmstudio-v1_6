from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth import create_session, revoke_session
from app.routers.exports import _enforce_assigned_version_export


ASSIGNMENT = {"author_id": "author", "reviewer_id": "reviewer", "approver_id": "approver", "revision": 1}


def request_as(username: str):
    token = create_session(username)
    request = Request({"type": "http", "method": "POST", "path": "/api/export/pdf", "headers": [(b"cookie", f"sermon_session={token}".encode())]})
    return request, token


def test_unversioned_draft_export_remains_supported():
    request, token = request_as("writer")
    try:
        _enforce_assigned_version_export({"text": "draft"}, request)
    finally:
        revoke_session(token)


def test_assigned_version_export_requires_approver_latest_and_valid_final_chain():
    request, token = request_as("approver")
    data = {"text": "final", "meta": {"sermon_id": 10, "version": 2}}
    try:
        with patch("app.routers.exports._collaboration_repository.get_assignment", return_value=ASSIGNMENT), \
             patch("app.routers.exports.user_exists", return_value=True), \
             patch("app.routers.exports.sermon_versions", return_value=[{"version": 1, "content": "old"}, {"version": 2, "content": "final"}]), \
             patch("app.routers.exports.sermon_review_state", return_value={
                 "locked": True,
                 "lock": {"integrity_ok": True, "locked_by": "approver"},
                 "history": [
                     {"reviewer": "reviewer", "status": "reviewed"},
                     {"reviewer": "approver", "status": "approved"},
                 ],
             }), \
             patch("app.routers.exports._collaboration_repository.list_workflow_events", return_value=[
                 {"assignment_revision": 1, "actor_id": "reviewer", "details": {"status": "reviewed"}},
                 {"assignment_revision": 1, "actor_id": "approver", "details": {"status": "approved"}},
             ]):
            _enforce_assigned_version_export(data, request)
            with pytest.raises(HTTPException) as error:
                _enforce_assigned_version_export({**data, "text": "edited after approval"}, request)
            assert error.value.status_code == 409
    finally:
        revoke_session(token)


@pytest.mark.parametrize(("actor", "version", "expected"), [
    ("reviewer", 2, 403),
    ("approver", 1, 409),
])
def test_assigned_version_export_denies_wrong_role_or_old_version(actor, version, expected):
    request, token = request_as(actor)
    try:
        with patch("app.routers.exports._collaboration_repository.get_assignment", return_value=ASSIGNMENT), \
             patch("app.routers.exports.user_exists", return_value=True), \
             patch("app.routers.exports.sermon_versions", return_value=[{"version": 1}, {"version": 2}]), \
             patch("app.routers.exports.sermon_review_state") as review_state:
            with pytest.raises(HTTPException) as error:
                _enforce_assigned_version_export({"meta": {"sermon_id": 10, "version": version}}, request)
            assert error.value.status_code == expected
            review_state.assert_not_called()
    finally:
        revoke_session(token)


def test_active_collaboration_schema_without_assignment_blocks_saved_export():
    request, token = request_as("approver")
    try:
        with patch("app.routers.exports._collaboration_repository.get_assignment", return_value=None):
            with pytest.raises(HTTPException) as error:
                _enforce_assigned_version_export({"meta": {"sermon_id": 10, "version": 2}}, request)
        assert error.value.status_code == 409
        assert error.value.detail["code"] == "collaboration_assignment_required"
    finally:
        revoke_session(token)
