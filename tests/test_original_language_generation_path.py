from pathlib import Path
from types import SimpleNamespace

from app.core import original_notes
from app.exporters import dashboard_html, original_language_markdown, pdf_document_html
from app.main import SermonRequest
from app.services import sermon_service


def _fake_client():
    client = SimpleNamespace(calls=[])

    def chat(model, system, user, **kwargs):
        client.calls.append({"model": model, "system": system, "user": user})
        return "요한복음 1:1 본문과 등록된 원어 근거를 따라 말씀을 전합니다."

    client.chat = chat
    return client


def test_registered_greek_evidence_survives_generation_and_prompt(monkeypatch):
    notes = original_notes("JHN 1:1")
    assert notes
    assert any(note["lexicon_enriched"] for note in notes)
    assert any(note["lexicon_source"] for note in notes)

    client = _fake_client()
    monkeypatch.setattr(
        sermon_service,
        "create_generation_audit",
        lambda **kwargs: {"id": "test-audit", "status": "ready_for_review", "warnings": []},
    )
    result = sermon_service.generate_sermon_workflow(
        SermonRequest(topic="말씀의 시작", details="", main_reference="JHN 1:1", minutes=15),
        client=client,
        passages=[{
            "translation": "SBLGNT", "language": "grc", "reference": "JHN 1:1",
            "text": "Ἐν ἀρχῇ ἦν ὁ λόγος", "license_note": "SBLGNT license",
        }],
        word_notes=notes,
        doctrine_notes=[],
        search_mode="문자검색",
        reading_cpm=330,
        clean_outline=None,
        select_generation_model=lambda _client, _requested: ("test-model", {}),
    )

    assert result["original_notes"] == notes
    assert "MorphGNT Strong Greek Dictionary XML" in client.calls[0]["user"]
    assert result["audit_id"] == "test-audit"


def test_original_language_sources_survive_export_renderers():
    note = {
        "reference": "JHN 1:1", "language": "grc", "lemma": "λόγος",
        "original": "λόγος", "transliteration": "logos", "gloss": "말씀",
        "morphology": "명사", "source": "SBLGNT", "license_note": "SBLGNT",
        "lexicon_source": "MorphGNT Strong Greek Dictionary XML",
        "lexicon_license_note": "CC0",
    }
    meta = {"topic": "테스트", "original_notes": [note]}
    markdown = original_language_markdown([note])
    dashboard = dashboard_html(sermon="원고", meta=meta, sources=[])
    pdf_html = pdf_document_html(sermon="원고", meta=meta, sources=[])

    for rendered in (markdown, dashboard, pdf_html):
        assert "MorphGNT Strong Greek Dictionary XML" in rendered
        assert "CC0" in rendered


def test_short_qwen_draft_gets_one_bounded_continuation(monkeypatch):
    notes = original_notes("JHN 1:1")
    client = _fake_client()
    responses = iter([
        "JHN 1:1 짧은 초안입니다.",
        "이어서 적용과 결론을 보강합니다.",
    ])
    client.chat = lambda model, system, user, **kwargs: (client.calls.append({"model": model, "system": system, "user": user}) or next(responses))
    monkeypatch.setattr(
        sermon_service,
        "create_generation_audit",
        lambda **kwargs: {"id": "test-audit-continuation", "status": "ready_for_review", "warnings": []},
    )
    result = sermon_service.generate_sermon_workflow(
        SermonRequest(topic="말씀의 시작", main_reference="JHN 1:1", minutes=15),
        client=client,
        passages=[{"translation": "SBLGNT", "language": "grc", "reference": "JHN 1:1", "text": "Ἐν ἀρχῇ ἦν ὁ λόγος", "license_note": "SBLGNT"}],
        word_notes=notes,
        doctrine_notes=[],
        search_mode="문자검색",
        reading_cpm=330,
        clean_outline=None,
        select_generation_model=lambda _client, _requested: ("qwen/qwen3-8b", {}),
    )

    assert result["continuation_count"] == 1
    assert len(client.calls) == 2
    assert "짧은 초안" in result["sermon"]
    assert "적용과 결론" in result["sermon"]
