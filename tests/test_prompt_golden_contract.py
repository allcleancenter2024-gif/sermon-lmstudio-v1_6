"""Golden contracts for prompt output before any prompt-module extraction."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.core import build_outline_prompt, build_sermon_prompt


PASSAGES = [{
    "translation": "WEB",
    "language": "en",
    "reference": "MAT 14:27",
    "text": "Take courage. It is I. Do not be afraid.",
    "license_note": "Public Domain",
}]
NOTES = [{
    "reference": "MAT 14:27",
    "language": "grc",
    "lemma": "θαρσέω",
    "transliteration": "tharseo",
    "gloss": "담대하다",
    "morphology": "verb",
    "source": "golden-source",
    "license_note": "golden-license",
    "lexicon_source": "golden-lexicon",
    "lexicon_license_note": "golden-lexicon-license",
}]
DOCTRINE = [{
    "tradition": "초교파 복음주의",
    "title": "Golden doctrine",
    "section": "1",
    "text": "검증된 교리 근거",
    "source_url": "golden://doctrine",
    "license_note": "reference-only",
}]
PAYLOAD = {
    "topic": "두려움 속의 믿음",
    "details": "golden detail",
    "main_reference": "MAT 14:27",
    "minutes": 15,
    "reading_cpm": 300,
    "audience": "청년",
    "tradition": "초교파 복음주의",
}


def _prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256((system + "\n---\n" + user).encode("utf-8")).hexdigest()


def test_sermon_prompt_golden_hash_and_evidence_provenance_are_stable():
    system, user = build_sermon_prompt(PAYLOAD, PASSAGES, NOTES, DOCTRINE)

    assert _prompt_hash(system, user) == "1db3df91149452d6d81322f3db6ee0d71358989c76d3ef3917d1a22e18764a16"
    assert "MAT 14:27" in user
    assert "golden-source" in user
    assert "사용조건: golden-license" in user
    assert "golden://doctrine" in user
    assert "직접 인용, 요약, 해설을 명확히 구분합니다." in system
    assert "구체적인 2026년 사건·통계·발언을 만들지 않습니다." in system


def test_outline_prompt_golden_hash_and_reference_allowlist_are_stable():
    system, user = build_outline_prompt(
        PAYLOAD,
        {"translations": PASSAGES, "context": [], "original_notes": NOTES},
        {"target_minutes": 15, "reading_cpm": 300, "segments": []},
    )

    assert _prompt_hash(system, user) == "6dc373e86c5a7e37c364e2a1214889be57d9c8f83e008cb34f2161a40c5edb23"
    assert '"MAT 14:27"' in user
    assert "허용 참조" in user
    assert "반드시 JSON 객체 하나만 출력하십시오." in system
    assert "등록되지 않은 단계는 기억으로 보충하지 말고 건너뛰며" in system


def test_sermon_prompt_module_boundary_has_no_core_or_web_dependency():
    source = (Path(__file__).parents[1] / "app" / "prompts" / "sermon.py").read_text(encoding="utf-8")

    assert "from app.core" not in source
    assert "fastapi" not in source.lower()
    assert "def build_sermon_prompt(" in source


def test_core_keeps_legacy_prompt_import_contract_as_facade():
    source = (Path(__file__).parents[1] / "app" / "core.py").read_text(encoding="utf-8")

    assert "from app.prompts.sermon import build_sermon_prompt as build_sermon_prompt_module" in source
    assert "return build_sermon_prompt_module(" in source


def test_outline_prompt_module_boundary_has_no_core_or_web_dependency():
    source = (Path(__file__).parents[1] / "app" / "prompts" / "outline.py").read_text(encoding="utf-8")

    assert "from app.core" not in source
    assert "fastapi" not in source.lower()
    assert "def build_outline_prompt(" in source


def test_core_keeps_legacy_outline_prompt_import_contract_as_facade():
    source = (Path(__file__).parents[1] / "app" / "core.py").read_text(encoding="utf-8")

    assert "from app.prompts.outline import build_outline_prompt as build_outline_prompt_module" in source
    assert "return build_outline_prompt_module(" in source


def test_prompt_callback_contracts_are_explicit_protocols():
    source = (Path(__file__).parents[1] / "app" / "prompts" / "contracts.py").read_text(encoding="utf-8")

    for name in (
        "class SermonTimePlan(Protocol)",
        "class CompactOutlineStudy(Protocol)",
        "class InterpretationFlowPrompt(Protocol)",
        "class GroundingBuilder(Protocol)",
    ):
        assert name in source
    assert "from app.core" not in source
