"""Authorization and account validation for sermon collaborator assignments."""

from __future__ import annotations

from typing import Callable

from app.repositories.collaboration import SermonCollaborationRepository


class SermonCollaborationService:
    """Keep account identity and assignment authorization outside persistence."""

    def __init__(
        self,
        repository: SermonCollaborationRepository,
        *,
        user_exists: Callable[[str], bool],
        is_admin: Callable[[str], bool],
    ):
        self.repository = repository
        self._user_exists = user_exists
        self._is_admin = is_admin

    def assign(
        self,
        *,
        sermon_id: int,
        author_id: str,
        reviewer_id: str,
        approver_id: str,
        actor_id: str,
        expected_revision: int,
    ) -> dict:
        actor = actor_id.strip().lower()
        if not actor or not self._user_exists(actor):
            raise PermissionError("로그인 계정을 확인할 수 없습니다.")
        if not self._is_admin(actor):
            raise PermissionError("협업 담당자 배정은 관리자만 할 수 있습니다.")
        normalized_ids = {
            author_id.strip().lower(),
            reviewer_id.strip().lower(),
            approver_id.strip().lower(),
        }
        if "" in normalized_ids or len(normalized_ids) != 3:
            raise ValueError("작성자·검토자·승인자는 서로 다른 계정이어야 합니다.")
        missing = sorted(user_id for user_id in normalized_ids if not self._user_exists(user_id))
        if missing:
            raise ValueError("등록되지 않은 협업 계정이 있습니다: " + ", ".join(missing))
        return self.repository.assign(
            sermon_id=sermon_id,
            author_id=author_id.strip().lower(),
            reviewer_id=reviewer_id.strip().lower(),
            approver_id=approver_id.strip().lower(),
            actor_id=actor,
            expected_revision=expected_revision,
        )


__all__ = ["SermonCollaborationService"]
