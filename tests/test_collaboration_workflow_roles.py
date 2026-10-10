from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth import create_session, revoke_session
from app.main import (
    SermonLockRequest,
    SermonReviewRequest,
    _current_review_events,
    create_version_review,
    export_final_hwpx,
    export_final_package,
    lock_version,
)


ASSIGNMENT = {"author_id": "author", "reviewer_id": "reviewer", "approver_id": "approver", "revision": 1}


def request_as(username: str) -> tuple[Request, str]:
    token = create_session(username)
    req = Request({"type": "http", "method": "POST", "path": "/api/test", "headers": [(b"cookie", f"sermon_session={token}".encode())]})
    return req, token


def test_assigned_reviewer_completes_review_then_distinct_approver_approves():
    reviewer_request, reviewer_token = request_as("reviewer")
    approver_request, approver_token = request_as("approver")
    try:
        with patch("app.main._collaboration_assignment_for_workflow", return_value=ASSIGNMENT), \
             patch("app.main.sermon_versions", return_value=[{"version": 3}]), \
             patch("app.main._current_review_events", return_value=[]), \
             patch("app.main.collaboration_repository.record_workflow_event"), \
             patch("app.main.add_sermon_review", return_value={"status": "reviewed", "created_at": "2026-10-08T12:00:00"}) as add_review, \
             patch("app.main.sermon_review_state", return_value={"history": []}):
            reviewed = create_version_review(8, 3, SermonReviewRequest(status="reviewed"), reviewer_request)
            assert reviewed["ok"]
            add_review.assert_called_once_with(8, 3, "reviewer", "reviewed", "")

        with patch("app.main._collaboration_assignment_for_workflow", return_value=ASSIGNMENT), \
             patch("app.main.sermon_versions", return_value=[{"version": 3}]), \
             patch("app.main._current_review_events", return_value=[{"actor_id": "reviewer", "details": {"status": "reviewed"}}]), \
             patch("app.main.collaboration_repository.record_workflow_event"), \
             patch("app.main.sermon_review_state", return_value={"history": [{"reviewer": "reviewer", "status": "reviewed"}]}), \
             patch("app.main.add_sermon_review", return_value={"status": "approved", "created_at": "2026-10-08T12:01:00"}) as add_approval:
            approved = create_version_review(8, 3, SermonReviewRequest(status="approved"), approver_request)
            assert approved["ok"]
            add_approval.assert_called_once_with(8, 3, "approver", "approved", "")
    finally:
        revoke_session(reviewer_token)
        revoke_session(approver_token)


@pytest.mark.parametrize(("actor", "status", "expected"), [
    ("author", "comment", 403),
    ("reviewer", "approved", 403),
    ("approver", "approved", 409),
])
def test_review_roles_and_review_first_order_are_enforced(actor, status, expected):
    req, token = request_as(actor)
    try:
        with patch("app.main._collaboration_assignment_for_workflow", return_value=ASSIGNMENT), \
             patch("app.main.sermon_versions", return_value=[{"version": 3}]), \
             patch("app.main._current_review_events", return_value=[]), \
             patch("app.main.sermon_review_state", return_value={"history": []}), \
             patch("app.main.add_sermon_review") as add_review:
            with pytest.raises(HTTPException) as error:
                create_version_review(8, 3, SermonReviewRequest(status=status), req)
            assert error.value.status_code == expected
            add_review.assert_not_called()
    finally:
        revoke_session(token)


def test_assigned_lock_and_exports_are_limited_to_approver_and_latest_version():
    author_request, author_token = request_as("author")
    approver_request, approver_token = request_as("approver")
    try:
        with patch("app.main._collaboration_assignment_for_workflow", return_value=ASSIGNMENT), \
             patch("app.main.sermon_versions", return_value=[{"version": 2}, {"version": 3}]), \
             patch("app.main._current_review_events", return_value=[{"actor_id": "reviewer", "details": {"status": "reviewed"}}, {"actor_id": "approver", "details": {"status": "approved"}}]), \
             patch("app.main.sermon_review_state", return_value={"history": [{"reviewer": "reviewer", "status": "reviewed"}, {"reviewer": "approver", "status": "approved"}]}), \
             patch("app.main.lock_sermon_version", return_value={"version": 3}) as lock:
            with pytest.raises(HTTPException) as error:
                lock_version(8, 3, SermonLockRequest(), author_request)
            assert error.value.status_code == 403
            assert lock.call_count == 0

            result = lock_version(8, 3, SermonLockRequest(), approver_request)
            assert result["ok"]
            lock.assert_called_once_with(8, 3, "approver")

        for exporter in (export_final_package, export_final_hwpx):
            with patch("app.main._collaboration_assignment_for_workflow", return_value=ASSIGNMENT), \
                 patch("app.main.sermon_versions", return_value=[{"version": 2}, {"version": 3}]), \
                 patch("app.main._current_review_events", return_value=[{"actor_id": "reviewer", "details": {"status": "reviewed"}}, {"actor_id": "approver", "details": {"status": "approved"}}]):
                with pytest.raises(HTTPException) as error:
                    exporter(8, 2, approver_request)
                assert error.value.status_code == 409
    finally:
        revoke_session(author_token)
        revoke_session(approver_token)


def test_role_revision_change_requires_a_new_sermon_version():
    changed_assignment = {**ASSIGNMENT, "revision": 2}
    with patch("app.main.collaboration_repository.list_workflow_events", return_value=[
        {"assignment_revision": 1, "actor_id": "reviewer", "details": {"version": 3, "status": "reviewed"}},
        {"assignment_revision": 1, "actor_id": "approver", "details": {"version": 3, "status": "approved"}},
    ]), patch("app.main.sermon_review_state", return_value={"history": [{"reviewer": "reviewer", "status": "reviewed"}]}):
        with pytest.raises(HTTPException) as error:
            _current_review_events(8, 3, changed_assignment)

    assert error.value.status_code == 409
    assert error.value.detail["code"] == "new_version_required"
