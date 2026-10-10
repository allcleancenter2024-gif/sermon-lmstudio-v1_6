from app.application.research_contracts import (
    CONTRACT_SCHEMA_VERSION,
    EvidenceClaim,
    EvidencePacket,
    LanguagePackage,
    OutputProfile,
    ResearchPackage,
    validate_contracts,
)


def test_research_and_language_contracts_are_pure_serializable_payloads():
    research = ResearchPackage(passage_structure={"reference": "요한복음 3:16"})
    language = LanguagePackage(keywords=({"lemma": "agape", "source_id": "greek-1"},))

    assert research.as_dict()["schema_version"] == CONTRACT_SCHEMA_VERSION
    assert research.as_dict()["passage_structure"]["reference"] == "요한복음 3:16"
    assert language.as_dict()["keywords"][0]["lemma"] == "agape"


def test_evidence_contract_requires_known_sources_and_valid_status():
    claim = EvidenceClaim(
        id="claim-1",
        section_id="structure",
        statement="본문의 중심 주장은 사랑이다.",
        claim_type="interpretation",
        source_ids=("source-1",),
        confidence=0.8,
        verification_status="verified",
    )
    packet = EvidencePacket(claims=(claim,), sources=({"id": "source-1", "license": "local"},))

    assert packet.validate() == []
    assert packet.as_dict()["claims"][0]["verification_status"] == "verified"

    missing = EvidencePacket(claims=(claim,), sources=())
    assert "missing sources" in missing.validate()[0]


def test_output_profile_rejects_unknown_formats_without_touching_db():
    profile = OutputProfile(enabled_formats=("html", "unknown"))
    assert profile.validate() == ["unsupported output format: unknown"]
    assert validate_contracts(ResearchPackage(), LanguagePackage(), EvidencePacket(), profile)["output"]
