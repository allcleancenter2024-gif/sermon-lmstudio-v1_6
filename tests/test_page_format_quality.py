from __future__ import annotations

from app.formatting.adapters import sermon_document
from app.formatting.format_router import render
from app.formatting.quality import accessibility_gate, markdown_quality, quality_score, source_integrity, validate_html_output
from pathlib import Path
import json


def _document():
    return sermon_document(
        sermon="## 본문\n진리 ἀλήθεια אמת",
        meta={"topic": "품질 샘플", "main_reference": "요 8:32"},
        sources=[{"id": "sblgnt-john-8-32", "reference": "요 8:32", "provider": "SBLGNT", "source_file": "John.xml"}],
    )


def test_html_structural_and_source_quality_gate():
    document = _document()
    output = render(document, "html")
    result = validate_html_output(output)
    assert result["ok"] is True
    assert source_integrity(document, output)["ok"] is True
    assert quality_score(document=document, rendered=output, format="html")["critical_failures"] == []
    assert accessibility_gate(output)["ok"] is True


def test_security_and_markdown_quality_gate():
    document = _document()
    markdown = render(document, "markdown")
    assert markdown_quality(markdown)["ok"] is True
    unsafe = render(sermon_document(sermon="<script>alert(1)</script>", meta={"topic": "안전"}), "html")
    assert validate_html_output(unsafe)["ok"] is True
    assert "<script>" not in unsafe


def test_source_loss_is_critical():
    document = _document()
    result = quality_score(document=document, rendered="# 품질 샘플\n본문", format="markdown")
    assert "source_integrity" in result["critical_failures"]


def test_all_pf3_golden_profiles_have_approved_metadata():
    root = Path("tests/page_format/golden")
    profiles = {path.name for path in root.iterdir() if path.is_dir()}
    expected = {"sermon", "greek-analysis", "dashboard", "comparison", "roadmap", "report", "teaching-material"}
    assert profiles == expected
    for profile in profiles:
        metadata = json.loads((root / profile / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["profile"] == profile
        assert metadata["approved_reason"] == "PF-3 initial baseline"
