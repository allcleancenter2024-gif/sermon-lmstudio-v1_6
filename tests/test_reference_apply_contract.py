from app.application.reference_apply_contract import build_reference_apply_plan
from app.application.reference_catalog import ReferenceCatalog, ReferenceSource


def _verified_catalog():
    return ReferenceCatalog(
        (
            ReferenceSource(
                "verified-1",
                "Verified source",
                "research",
                "https://example.test/verified",
                citation="Example citation",
                license_note="Example license",
                verification_status="verified",
                allowed_for_application=True,
            ),
        ),
        ("example.test",),
    )


def test_dry_run_rejects_verified_source_without_explicit_user_approval():
    plan = build_reference_apply_plan(_verified_catalog(), ["verified-1"])

    assert plan.approved_source_ids == ()
    assert plan.rejected_source_ids == ("verified-1",)
    assert plan.dry_run is True
    assert plan.requires_backup is True
    assert plan.mutates_data is False


def test_explicit_approval_only_changes_the_plan_not_data():
    plan = build_reference_apply_plan(_verified_catalog(), ["verified-1"], user_approved=True)

    assert plan.approved_source_ids == ("verified-1",)
    assert plan.rejected_source_ids == ()
    assert plan.as_dict()["mutates_data"] is False


def test_unknown_and_unverified_sources_are_rejected():
    catalog = ReferenceCatalog(
        (_verified_catalog().sources[0], ReferenceSource("review-1", "Review", "research", "https://example.test/review", verification_status="needs_review")),
        ("example.test",),
    )
    plan = build_reference_apply_plan(catalog, ["missing", "review-1"])

    assert plan.approved_source_ids == ()
    assert plan.rejected_source_ids == ("missing", "review-1")
    assert any("source not found" in reason for reason in plan.reasons)
    assert any("not verified" in reason for reason in plan.reasons)
