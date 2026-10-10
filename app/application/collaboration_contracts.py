"""Pure contracts for account-assigned sermon collaboration.

These contracts define identity, version, and concurrency invariants without
introducing database changes or HTTP behavior. Persistence must use an
explicit migration and must not activate until legacy ownership is resolved.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar


COLLABORATION_SCHEMA_VERSION = 1
REVIEW_DECISIONS = frozenset({"comment", "changes_requested", "reviewed"})


@dataclass(frozen=True)
class SermonAssignment:
    """Role assignment for one sermon; the author is its owner."""

    sermon_id: int
    author_id: str
    reviewer_id: str
    approver_id: str
    revision: int = 1

    schema_version: ClassVar[int] = COLLABORATION_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.sermon_id <= 0:
            errors.append("sermon_id must be positive")
        if self.revision <= 0:
            errors.append("revision must be positive")
        ids = [self.author_id.strip(), self.reviewer_id.strip(), self.approver_id.strip()]
        if any(not user_id for user_id in ids):
            errors.append("author_id, reviewer_id, and approver_id are required")
        elif len(set(ids)) != 3:
            errors.append("author, reviewer, and approver must be different accounts")
        return errors

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema_version"] = self.schema_version
        return result


@dataclass(frozen=True)
class ReviewDecision:
    """Review event bound to the assigned reviewer and one immutable version."""

    sermon_id: int
    version: int
    actor_id: str
    status: str

    def validate(self, assignment: SermonAssignment) -> list[str]:
        errors: list[str] = []
        if self.sermon_id <= 0 or self.version <= 0:
            errors.append("sermon_id and version must be positive")
        if self.sermon_id != assignment.sermon_id:
            errors.append("review sermon_id does not match assignment")
        if not self.actor_id.strip() or self.actor_id.strip() != assignment.reviewer_id.strip():
            errors.append("review actor must be the assigned reviewer")
        if self.status not in REVIEW_DECISIONS:
            errors.append(f"unsupported review status: {self.status}")
        return errors


@dataclass(frozen=True)
class VersionApproval:
    """Approval requires the assigned reviewer and approver on the latest version."""

    sermon_id: int
    version: int
    reviewer_id: str
    approver_id: str

    def validate(self, assignment: SermonAssignment, *, latest_version: int, reviewed_version: int) -> list[str]:
        errors: list[str] = []
        if self.sermon_id != assignment.sermon_id or self.sermon_id <= 0:
            errors.append("approval sermon_id does not match assignment")
        if self.version <= 0 or self.version != latest_version:
            errors.append("approval must reference the latest sermon version")
        if reviewed_version != self.version:
            errors.append("the same version must be reviewed before approval")
        if self.reviewer_id.strip() != assignment.reviewer_id.strip():
            errors.append("reviewer_id does not match the assigned reviewer")
        if self.approver_id.strip() != assignment.approver_id.strip():
            errors.append("approver_id does not match the assigned approver")
        if not self.reviewer_id.strip() or not self.approver_id.strip() or self.reviewer_id.strip() == self.approver_id.strip():
            errors.append("reviewer and approver must be different accounts")
        return errors


def check_expected_revision(expected_revision: int, current_revision: int) -> list[str]:
    """Return a conflict when a client tries to write from a stale revision."""
    if expected_revision <= 0 or current_revision <= 0:
        return ["expected_revision and current_revision must be positive"]
    if expected_revision != current_revision:
        return ["expected_revision_mismatch"]
    return []


__all__ = [
    "COLLABORATION_SCHEMA_VERSION",
    "REVIEW_DECISIONS",
    "ReviewDecision",
    "SermonAssignment",
    "VersionApproval",
    "check_expected_revision",
]
