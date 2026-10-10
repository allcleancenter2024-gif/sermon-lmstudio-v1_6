from app.application.canary_adapters import build_one_section
from app.application.canary_builders import StructureBuilder
from app.application.section_contracts import SectionRegenerationRequest


def _study(reference, related):
    return {
        "reference": reference,
        "translations": [
            {
                "translation": "TEST",
                "language": "ko",
                "reference": reference,
                "text": "등록된 중심 본문",
                "license_note": "test-only",
            }
        ],
        "context": [{"reference": "테스트 1:2", "text": "앞뒤 절"}],
        "related": list(related or []),
        "warnings": [],
        "counts": {"translations": 1, "context": 1, "related": len(related or [])},
    }


def test_structure_builder_reuses_passage_study_without_provider_or_database_imports():
    builder = StructureBuilder(_study)
    request = SectionRegenerationRequest(
        "structure",
        {"reference": "테스트 1:1", "related": [{"reference": "테스트 2:1"}]},
        {"source_ids": ["source-1"]},
        "source-snapshot-1",
    )

    result = build_one_section(request, builder)

    assert result.status == "ready"
    assert result.render_data["title"] == "본문의 위치와 구조"
    assert result.render_data["translations"][0]["reference"] == "테스트 1:1"
    assert result.render_data["source_ids"] == ["source-1"]


def test_structure_builder_fails_closed_when_main_passage_is_not_registered():
    builder = StructureBuilder(lambda reference, related: {
        "translations": [], "context": [], "related": [], "warnings": ["본문 없음"], "counts": {}
    })
    request = SectionRegenerationRequest(
        "structure", {"reference": "없는책 1:1"}, {"source_ids": []}
    )

    result = build_one_section(request, builder)

    assert result.status == "invalid"
    assert result.errors == ("registered main-passage text is required",)


def test_structure_builder_rejects_missing_reference_before_loading_study():
    called = False

    def loader(reference, related):
        nonlocal called
        called = True
        return {}

    result = build_one_section(
        SectionRegenerationRequest("structure", {}, {}),
        StructureBuilder(loader),
    )

    assert result.status == "failed"
    assert "reference is required" in result.errors[0]
    assert called is False
