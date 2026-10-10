from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth import create_session, revoke_session
from app.main import (
    SermonLockRequest,
    SermonReviewRequest,
    create_version_review,
    lock_version,
)


def _request(token: str | None) -> Request:
    headers = [(b"cookie", f"sermon_session={token}".encode())] if token else []
    return Request({"type": "http", "method": "POST", "path": "/api/test", "headers": headers})


def test_review_actor_comes_from_session_not_request_body():
    token = create_session("reviewer-account")
    try:
        with patch("app.main.add_sermon_review", return_value={"reviewer": "reviewer-account"}) as add_review, \
             patch("app.main.sermon_review_state", return_value={"state": "approved"}):
            result = create_version_review(
                10,
                2,
                SermonReviewRequest(reviewer="forged-admin", status="approved"),
                _request(token),
            )

        assert add_review.call_args.args == (10, 2, "reviewer-account", "approved", "")
        assert result["review"]["reviewer"] == "reviewer-account"
    finally:
        revoke_session(token)


def test_lock_actor_comes_from_session_not_request_body():
    token = create_session("approver-account")
    try:
        with patch("app.main.lock_sermon_version", return_value={"locked_by": "approver-account"}) as lock, \
             patch("app.main.sermon_review_state", return_value={"state": "locked"}):
            result = lock_version(
                10,
                2,
                SermonLockRequest(locked_by="forged-admin"),
                _request(token),
            )

        assert lock.call_args.args == (10, 2, "approver-account")
        assert result["lock"]["locked_by"] == "approver-account"
    finally:
        revoke_session(token)


@pytest.mark.parametrize(
    ("handler", "payload"),
    [
        (create_version_review, SermonReviewRequest(reviewer="forged-user", status="approved")),
        (lock_version, SermonLockRequest(locked_by="forged-user")),
    ],
)
def test_review_and_lock_reject_missing_session_even_when_body_names_actor(handler, payload):
    with pytest.raises(HTTPException) as error:
        handler(10, 2, payload, _request(None))

    assert error.value.status_code == 401
    assert error.value.detail["code"] == "auth_required"
