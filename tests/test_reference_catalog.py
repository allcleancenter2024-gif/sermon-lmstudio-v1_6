from app.application.reference_catalog import ReferenceCatalog, ReferenceSource


def test_unverified_source_is_visible_but_not_applyable():
    source = ReferenceSource("ebible", "eBible", "bible", "https://ebible.org/", verification_status="needs_review")
    catalog = ReferenceCatalog((source,), ("ebible.org",))

    assert catalog.validate() == []
    assert catalog.applyable() == ()
    assert catalog.as_dict()["sources"][0]["can_apply"] is False


def test_verified_source_requires_provenance_and_license_before_apply():
    source = ReferenceSource(
        "openscriptures",
        "Open Scriptures",
        "language",
        "https://hb.openscriptures.org/",
        citation="Open Scriptures Hebrew Bible",
        license_note="Review the source license before use",
        verification_status="verified",
        allowed_for_application=True,
    )
    catalog = ReferenceCatalog((source,), ("hb.openscriptures.org",))

    assert catalog.validate() == []
    assert catalog.applyable() == (source,)


def test_invalid_application_and_duplicate_ids_are_rejected():
    source = ReferenceSource(
        "same",
        "Unverified",
        "research",
        "https://example.test/source",
        allowed_for_application=True,
    )
    catalog = ReferenceCatalog((source, source), ("example.test",))

    errors = catalog.validate()
    assert "source id must be unique" in errors
    assert any("application requires verified source" in error for error in errors)
    assert any("application requires citation" in error for error in errors)
    assert any("application requires license_note" in error for error in errors)


def test_unsafe_url_and_unapproved_domain_are_rejected():
    source = ReferenceSource("bad", "Bad", "other", "javascript:alert(1)")
    assert any("url must use http or https" in error for error in source.validate())

    source = ReferenceSource("other", "Other", "other", "https://not-allowed.test/")
    assert any("url domain is not in the catalog allowlist" in error for error in source.validate(("allowed.test",)))
