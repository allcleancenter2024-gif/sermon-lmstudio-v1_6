from app.application.research_persistence_contracts import (
    PROPOSED_TABLES,
    RenderSnapshot,
    ResearchSectionRecord,
)


def test_gate1_contract_defines_all_proposed_tables_without_database_access():
    assert PROPOSED_TABLES == (
        "sermon_research_packages",
        "sermon_sections",
        "sermon_claims",
        "sermon_evidence_links",
        "sermon_assets",
        "sermon_render_snapshots",
        "sermon_review_events",
    )


def test_section_record_enforces_version_status_coverage_and_approval():
    valid = ResearchSectionRecord(
        project_id=1,
        section_type="structure",
        version=1,
        status="approved",
        content={"summary": "본문 구조"},
        source_coverage=1.0,
        quality_status="passed",
        review_status="approved",
        source_snapshot_id="source-1",
    )
    assert valid.validate() == []
    assert valid.as_dict()["schema_version"] == 1

    invalid = ResearchSectionRecord(
        project_id=0,
        section_type="",
        version=0,
        status="ready",
        content={},
        source_coverage=1.1,
        review_status="approved",
    )
    errors = invalid.validate()
    assert "project_id must be positive" in errors
    assert "ready section requires content" in errors
    assert "approved review requires approved section status" in errors


def test_render_snapshot_requires_reproducible_version_identifiers():
    snapshot = RenderSnapshot(
        project_id=7,
        research_version=2,
        language_version=3,
        sermon_version=4,
        evidence_version=5,
        renderer_version="page-format-v2",
        section_versions=(("structure", 2), ("verse_commentary", 1)),
        output_profile={"enabled_formats": ["html", "markdown"]},
        created_at="2026-10-02T12:00:00+09:00",
    )
    assert snapshot.validate() == []
    assert snapshot.as_dict()["section_versions"] == {"structure": 2, "verse_commentary": 1}

    duplicate = RenderSnapshot(
        project_id=7,
        research_version=1,
        language_version=1,
        sermon_version=1,
        evidence_version=1,
        renderer_version="page-format-v2",
        section_versions=(("structure", 1), ("structure", 2)),
        output_profile={"enabled_formats": ["html"]},
        created_at="2026-10-02T12:00:00+09:00",
    )
    assert "section_versions must contain unique section ids" in duplicate.validate()
