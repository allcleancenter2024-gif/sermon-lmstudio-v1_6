from pathlib import Path
import zipfile

from app.exporters import write_hwpx


ROOT = Path(__file__).resolve().parents[1]


def test_preview_allows_current_draft_as_review_only_exception():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert "value=\"draft\"" in js
    assert "검토용 초안 · 최종 잠금 전" in js
    assert "previewMode==='draft'" in js
    assert "검토용 초안은 최종 승인·잠금 후에만 다운로드할 수 있습니다." in js
    assert "검토용 초안은 최종 승인·잠금 후에만 인쇄할 수 있습니다." in js
    assert "previewHwpx" in js
    assert "/export-hwpx" in js
    assert "현재 생성된 초안은 예외적으로 검토용으로 표시" in html


def test_preview_draft_is_not_exportable_or_printable_by_default():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert "forEach(id=>$(id).disabled=draft)" in js
    assert "if(previewMode==='draft')" in js
    assert "sermonPrintDocument" in js


def test_manual_revision_creates_separate_version_and_reaudits():
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert "saveManualRevision" in js
    assert "revision_parent_version:Number(v)" in js
    assert "revision_method:'manual'" in js
    assert "audit_id:null" in js
    assert "/reaudit" in js
    assert "수동 수정본을 새 버전으로 저장" in html


def test_hwpx_export_is_a_valid_uncompressed_mimetype_package(tmp_path):
    output = tmp_path / "sermon.hwpx"
    write_hwpx(output, sermon="# 본문 제목\n설교 내용", meta={"topic": "시험 설교", "main_reference": "요 8:32"})

    with zipfile.ZipFile(output) as archive:
        assert archive.namelist()[0] == "mimetype"
        assert archive.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/hwp+zip"
        section = archive.read("Contents/section0.xml").decode("utf-8")
        assert "시험 설교" in section
        assert "설교 내용" in section


def test_optimization_status_is_visible_in_both_project_panels():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

    assert "[2026-09-04 운영 안정화 작업 완료]" in html
    assert "<b>361</b>" in html
    assert "installGuidePanel" in html
    assert "정상상태 복구" in html
    assert "generationProgressEta" in html
    assert "outlineProgressEta" in html
    assert "ragProgressEta" in html
    assert "formatProgressEta" in js
    assert "optimizedWorkSummaryMarkdown" in js
    assert "sermon-lmstudio-work-summary-v40.9.10.md" in js
