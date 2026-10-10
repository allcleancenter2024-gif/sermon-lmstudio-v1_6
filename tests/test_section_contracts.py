import json
from pathlib import Path

from app.application.section_contracts import SectionRegenerationRequest, validate_section_result
from app.application.section_registry import SectionBuildResult


def test_canary_section_fixture_defines_independent_regeneration_inputs():
    payload = json.loads((Path(__file__).parent / "fixtures" / "canary_section_contracts.json").read_text(encoding="utf-8"))
    requests = [SectionRegenerationRequest(section_id, payload["context"], payload["evidence"]) for section_id in payload["sections"]]

    assert all(request.validate() == [] for request in requests)
    retried = requests[2].retry()
    assert retried.section_id == "verse_commentary"
    assert retried.attempt == 1
    assert requests[2].attempt == 0


def test_section_output_contract_requires_payload_or_error_by_status():
    assert validate_section_result(SectionBuildResult("structure", "ready", render_data={"heading": "ok"})) == []
    assert validate_section_result(SectionBuildResult("structure", "failed", errors=("retry",))) == []
    assert "render_data" in validate_section_result(SectionBuildResult("structure", "ready"))[0]
    assert "errors" in validate_section_result(SectionBuildResult("structure", "invalid"))[0]
