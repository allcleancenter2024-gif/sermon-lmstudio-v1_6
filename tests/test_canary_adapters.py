import json
from pathlib import Path

from app.application.canary_adapters import build_fixture_sections, build_one_section
from app.application.section_contracts import SectionRegenerationRequest


class _FixtureBuilder:
    def __init__(self, section_id, failure=None):
        self.section_id = section_id
        self.failure = failure

    def build(self, context, evidence):
        if self.failure:
            raise self.failure
        return {"section_id": self.section_id, "reference": context["reference"], "sources": evidence["source_ids"]}

    def validate(self, result):
        return []

    def to_render_data(self, result):
        return result


def _fixture_requests():
    payload = json.loads((Path(__file__).parent / "fixtures" / "canary_section_contracts.json").read_text(encoding="utf-8"))
    return tuple(SectionRegenerationRequest(section_id, payload["context"], payload["evidence"], "snapshot-fixture") for section_id in payload["sections"])


def test_fixture_adapters_build_each_canary_section_without_external_dependencies():
    requests = _fixture_requests()
    builders = {request.section_id: _FixtureBuilder(request.section_id) for request in requests}

    results = build_fixture_sections(requests, builders)
    assert [result.status for result in results] == ["ready"] * 5
    assert results[0].render_data["reference"] == "fixture-ref-1"


def test_one_fixture_adapter_failure_does_not_change_other_requests():
    requests = _fixture_requests()
    builders = {request.section_id: _FixtureBuilder(request.section_id) for request in requests}
    builders["verse_commentary"] = _FixtureBuilder("verse_commentary", RuntimeError("fixture failure"))

    results = build_fixture_sections(requests, builders)
    assert results[2].status == "failed"
    assert "fixture failure" in results[2].errors[0]
    assert results[0].status == "ready"
    assert results[3].status == "ready"


def test_invalid_request_is_rejected_before_builder_execution():
    request = SectionRegenerationRequest("unknown", {}, {})
    result = build_one_section(request, _FixtureBuilder("unknown"))

    assert result.status == "invalid"
    assert "unsupported section" in result.errors[0]
