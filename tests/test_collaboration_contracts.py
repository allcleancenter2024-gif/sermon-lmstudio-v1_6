from app.application.collaboration_contracts import (
    ReviewDecision,
    SermonAssignment,
    VersionApproval,
    check_expected_revision,
)


def _assignment() -> SermonAssignment:
    return SermonAssignment(sermon_id=12, author_id="author", reviewer_id="reviewer", approver_id="approver")


def test_assignment_requires_three_distinct_accounts():
    assert _assignment().validate() == []
    assignment = SermonAssignment(12, "same", "same", "approver")
    assert "author, reviewer, and approver must be different accounts" in assignment.validate()


def test_review_is_bound_to_assigned_reviewer_and_sermon():
    assignment = _assignment()
    assert ReviewDecision(12, 3, "reviewer", "reviewed").validate(assignment) == []
    assert "review actor must be the assigned reviewer" in ReviewDecision(12, 3, "author", "reviewed").validate(assignment)
    assert "review sermon_id does not match assignment" in ReviewDecision(13, 3, "reviewer", "reviewed").validate(assignment)


def test_approval_requires_matching_assignment_and_reviewed_latest_version():
    assignment = _assignment()
    approved = VersionApproval(12, 3, "reviewer", "approver")
    assert approved.validate(assignment, latest_version=3, reviewed_version=3) == []
    assert "approval must reference the latest sermon version" in approved.validate(
        assignment, latest_version=4, reviewed_version=3
    )
    assert "the same version must be reviewed before approval" in approved.validate(
        assignment, latest_version=3, reviewed_version=2
    )


def test_stale_revision_is_reported_as_a_conflict_contract():
    assert check_expected_revision(4, 4) == []
    assert check_expected_revision(3, 4) == ["expected_revision_mismatch"]
    assert check_expected_revision(0, 4) == ["expected_revision and current_revision must be positive"]
