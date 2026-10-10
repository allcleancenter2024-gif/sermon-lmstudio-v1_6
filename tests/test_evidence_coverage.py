import json
from pathlib import Path

from app.application.evidence_coverage import evaluate_evidence_coverage
from app.application.research_contracts import EvidenceClaim, EvidencePacket


def _packet_from_fixture() -> EvidencePacket:
    payload = json.loads((Path(__file__).parent / "fixtures" / "canary_evidence_coverage.json").read_text(encoding="utf-8"))
    return EvidencePacket(
        claims=tuple(EvidenceClaim(**claim) for claim in payload["claims"]),
        sources=tuple(payload["sources"]),
    )


def test_anonymized_canary_fixture_has_complete_citation_and_license_coverage():
    report = evaluate_evidence_coverage(_packet_from_fixture())

    assert report["status"] == "pass"
    assert report["citation_coverage"] == 1.0
    assert report["license_coverage"] == 1.0
    assert report["missing_source_ids"] == []


def test_coverage_flags_missing_metadata_without_mutating_packet():
    packet = EvidencePacket(
        claims=(EvidenceClaim("claim-1", "structure", "주장", "interpretation", ("source-1",)),),
        sources=({"id": "source-1", "reference": "fixture-ref"},),
    )

    report = evaluate_evidence_coverage(packet)
    assert report["status"] == "needs_review"
    assert report["citation_missing_source_ids"] == []
    assert report["license_missing_source_ids"] == ["source-1"]
    assert packet.sources[0]["id"] == "source-1"
