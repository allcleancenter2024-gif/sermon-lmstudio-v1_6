from app.application.reference_catalog import ReferenceCatalog, ReferenceSource
from app.application.reference_review import review_reference_catalog


def test_review_reports_unverified_metadata_without_network_access():
    catalog = ReferenceCatalog((ReferenceSource("review-1", "Review", "research", "https://example.test/"),), ("example.test",))

    result = review_reference_catalog(catalog)

    assert result["ready"] is False
    assert result["network_checked"] is False
    assert result["persistent_changes"] is False
    assert result["applyable_source_ids"] == []
    assert any(item["message"] == "verification status requires review" for item in result["findings"])


def test_review_passes_only_a_complete_verified_catalog():
    source = ReferenceSource(
        "verified-1",
        "Verified",
        "research",
        "https://example.test/verified",
        citation="Example citation",
        license_note="Example license",
        verification_status="verified",
        allowed_for_application=True,
    )

    result = review_reference_catalog(ReferenceCatalog((source,), ("example.test",)))

    assert result["ready"] is True
    assert result["findings"] == []
    assert result["applyable_source_ids"] == ["verified-1"]
