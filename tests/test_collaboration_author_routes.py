from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth import create_session, revoke_session
from app.main import (
    SermonSaveRequest,
    reaudit_version,
    save_sermon_version,
    saved_versions,
    _require_collaboration_reader,
)


ASSIGNMENT = {"author_id": "author", "reviewer_id": "reviewer", "approver_id": "approver"}


def request_as(username: str):
    token = create_session(username)
    return Request({"type": "http", "method": "POST", "path": "/api/test", "headers": [(b"cookie", f"sermon_session={token}".encode())]}), token


@pytest.mark.parametrize("handler,args", [
    (save_sermon_version, (SermonSaveRequest(topic="test", content="body", sermon_id=9),)),
    (reaudit_version, (9, 2)),
])
def test_non_author_cannot_create_or_reaudit_assigned_sermon(handler, args):
    request, token = request_as("reviewer")
    try:
        with patch("app.main._collaboration_assignment_for_workflow", return_value=ASSIGNMENT), \
             patch("app.main.save_sermon") as save, \
             patch("app.main.reaudit_sermon_version") as reaudit:
            with pytest.raises(HTTPException) as error:
                handler(*args, request)
        assert error.value.status_code == 403
        save.assert_not_called()
        reaudit.assert_not_called()
    finally:
        revoke_session(token)


def test_non_participant_cannot_read_assigned_versions():
    request, token = request_as("outsider")
    try:
        with patch("app.main._collaboration_assignment_for_workflow", return_value=ASSIGNMENT), \
             patch("app.main.sermon_versions") as versions:
            with pytest.raises(HTTPException) as error:
                saved_versions(9, request)
        assert error.value.status_code == 404
        versions.assert_not_called()
    finally:
        revoke_session(token)


def test_admin_can_read_assignment_history_without_gaining_write_role():
    with patch("app.main._collaboration_assignment_for_workflow", return_value=ASSIGNMENT), \
         patch("app.main.is_admin", return_value=True):
        assert _require_collaboration_reader(9, "admin") == ASSIGNMENT
        with pytest.raises(HTTPException) as error:
            from app.main import _require_collaboration_role
            _require_collaboration_role(9, "admin", "approver")
    assert error.value.status_code == 403
