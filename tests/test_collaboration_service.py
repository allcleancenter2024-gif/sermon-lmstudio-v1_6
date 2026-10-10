from __future__ import annotations

import pytest

from app.application.collaboration_service import SermonCollaborationService


class FakeRepository:
    def __init__(self):
        self.calls = []

    def assign(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


def make_service(*, users=None, admins=None):
    repository = FakeRepository()
    users = users or {"admin", "writer", "reviewer", "approver"}
    admins = admins or {"admin"}
    service = SermonCollaborationService(
        repository,
        user_exists=lambda username: username in users,
        is_admin=lambda username: username in admins,
    )
    return service, repository


def assignment_args(**overrides):
    args = {
        "sermon_id": 7,
        "author_id": "WRITER",
        "reviewer_id": "reviewer",
        "approver_id": "approver",
        "actor_id": "ADMIN",
        "expected_revision": 0,
    }
    args.update(overrides)
    return args


def test_admin_assignment_validates_and_normalizes_all_accounts():
    service, repository = make_service()
    result = service.assign(**assignment_args())

    assert result["actor_id"] == "admin"
    assert result["author_id"] == "writer"
    assert repository.calls == [result]


def test_non_admin_cannot_assign_collaborators():
    service, repository = make_service()

    with pytest.raises(PermissionError):
        service.assign(**assignment_args(actor_id="writer"))

    assert repository.calls == []


def test_unknown_actor_and_collaborator_are_rejected_before_persistence():
    service, repository = make_service()

    with pytest.raises(PermissionError):
        service.assign(**assignment_args(actor_id="unknown"))
    with pytest.raises(ValueError, match="등록되지 않은"):
        service.assign(**assignment_args(approver_id="unknown"))

    assert repository.calls == []


def test_duplicate_roles_are_rejected_before_persistence():
    service, repository = make_service()

    with pytest.raises(ValueError, match="서로 다른 계정"):
        service.assign(**assignment_args(approver_id="reviewer"))

    assert repository.calls == []
