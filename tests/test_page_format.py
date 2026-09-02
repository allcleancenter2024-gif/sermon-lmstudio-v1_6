from __future__ import annotations

from app.formatting.adapters import analysis_document, report_document, sermon_document
from app.formatting.document_model import ContentBlock, Document, Section, Source, validate_document
from app.formatting.format_router import page_format_v2_enabled, render
from app.formatting.format_router import render_to_path
from app.formatting.profiles import PAGE_PROFILES, resolve_profile


def test_document_model_validation_and_duplicate_detection():
    document = Document("report", "검증", sections=[Section("one", "report", content=[ContentBlock("paragraph", "내용")])], sources=[Source("s1", reference="요 8:32")])
    assert validate_document(document) == []
    document.sections.append(Section("one", "report"))
    assert any("duplicate section id" in error for error in validate_document(document))


def test_adapters_preserve_source_provenance_and_unicode():
    document = sermon_document(sermon="진리 ἀλήθεια אמת", meta={"topic": "제목", "main_reference": "요 8:32"}, sources=[{"reference": "요 8:32", "provider": "SBLGNT", "source_file": "John.xml"}])
    assert document.sources[0].metadata["source_file"] == "John.xml"
    assert "ἀλήθεια" in render(document, "markdown")
    assert "אמת" in render(document, "html")


def test_profile_registry_and_safe_fallback():
    assert set(("sermon", "analysis", "dashboard", "comparison", "roadmap", "report", "teaching-material")) <= set(PAGE_PROFILES)
    assert resolve_profile("unknown").name == "report"
    assert analysis_document(title="원어", items=[{"reference": "John 8:32", "source": {"version": "SBLGNT"}}]).document_type == "analysis"
    assert report_document(title="보고서", summary="요약").document_type == "report"


def test_format_router_renders_standalone_safe_html_and_dashboard():
    document = sermon_document(sermon="<script>alert(1)</script>\n본문", meta={"topic": "설교"})
    html = render(document, "html")
    dashboard = render(document, "dashboard")
    assert html.startswith("<!doctype html>")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>" not in html
    assert 'data-page-profile="dashboard"' in dashboard


def test_page_format_flag_defaults_to_legacy(monkeypatch):
    monkeypatch.delenv("PAGE_FORMAT_V2", raising=False)
    assert page_format_v2_enabled() is True
    monkeypatch.setenv("PAGE_FORMAT_V2", "true")
    assert page_format_v2_enabled() is True


def test_legacy_export_router_has_opt_in_page_format_switch():
    source = (__import__("pathlib").Path("app/routers/exports.py")).read_text(encoding="utf-8")
    assert "page_format_v2_enabled()" in source
    assert "render(_page_document(data), selection[\"format\"], selection[\"profile\"], {\"theme\": selection[\"theme\"]})" in source
    assert "selection = _page_selection(data, \"pdf\")" in source
    assert "render_to_path(_page_document(data), selection[\"format\"], path" in source


def test_invalid_format_is_rejected():
    document = sermon_document(sermon="본문", meta={"topic": "설교"})
    try:
        render(document, "epub")
    except ValueError as exc:
        assert "지원하지 않는 page format" in str(exc)
    else:
        raise AssertionError("unsupported format must fail")


def test_pdf_and_docx_adapters_reuse_legacy_exporters(monkeypatch, tmp_path):
    document = sermon_document(sermon="본문", meta={"topic": "설교"})
    calls = []

    def fake_docx(path, *, sermon, meta):
        calls.append(("docx", sermon, meta["topic"])); path.write_bytes(b"docx")

    def fake_pdf(path, *, sermon, meta, sources):
        calls.append(("pdf", sermon, meta["topic"], sources)); path.write_bytes(b"pdf")

    monkeypatch.setattr("app.exporters.write_docx", fake_docx)
    monkeypatch.setattr("app.exporters.write_pdf", fake_pdf)
    render_to_path(document, "docx", tmp_path / "out.docx")
    render_to_path(document, "pdf", tmp_path / "out.pdf")
    assert (tmp_path / "out.docx").read_bytes() == b"docx"
    assert (tmp_path / "out.pdf").read_bytes() == b"pdf"
    assert [item[0] for item in calls] == ["docx", "pdf"]
