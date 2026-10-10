from app.application.reference_fixture import validate_reference_fixture


def test_fixture_requires_review_evidence_for_verified_source():
    payload = [{
        "id": "source-1",
        "label": "Source",
        "category": "research",
        "url": "https://example.test/",
        "citation": "Citation",
        "license_note": "License",
        "verification_status": "verified",
    }]

    errors = validate_reference_fixture(payload)

    assert "item[0]: verified source requires approval_ref" in errors
    assert "item[0]: verified source requires reviewed_by" in errors
    assert "item[0]: verified source requires reviewed_at" in errors


def test_fixture_accepts_reviewed_verified_source_without_persisting_it():
    payload = [{
        "id": "source-1",
        "label": "Source",
        "category": "research",
        "url": "https://example.test/",
        "citation": "Citation",
        "license_note": "License",
        "verification_status": "verified",
        "approval_ref": "ticket-1",
        "reviewed_by": "reviewer",
        "reviewed_at": "2026-10-01T00:00:00+09:00",
        "allowed_for_application": True,
    }]

    assert validate_reference_fixture(payload) == []


def test_fixture_rejects_empty_duplicate_and_unverified_application():
    assert validate_reference_fixture([]) == ["fixture must be a non-empty list"]
    payload = [
        {"id": "same", "label": "S", "category": "c", "url": "https://example.test", "citation": "c", "license_note": "l", "verification_status": "needs_review", "allowed_for_application": True},
        {"id": "same", "label": "S2", "category": "c", "url": "https://example.test/2", "citation": "c", "license_note": "l", "verification_status": "needs_review"},
    ]

    errors = validate_reference_fixture(payload)
    assert "item[0]: application requires verified status" in errors
    assert "item[1]: duplicate id same" in errors
