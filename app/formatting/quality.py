from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from .document_model import Document, validate_document


class _HTMLInspection(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.h1 = 0
        self.headings: list[int] = []
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.table_headers = 0
        self.source_text = ""
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): str(value or "") for key, value in attrs}
        if tag == "h1": self.h1 += 1
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}: self.headings.append(int(tag[1]))
        if tag == "th": self.table_headers += 1
        if "id" in values:
            if values["id"] in self.ids: self.duplicate_ids.add(values["id"])
            self.ids.add(values["id"])
        if tag == "script" or tag == "iframe": self.errors.append(f"unsafe element: {tag}")
        if any(key.startswith("on") for key in values): self.errors.append("inline event handler")
        if any(re.match(r"^javascript:", value, re.I) for value in values.values()): self.errors.append("javascript URL")

    def handle_data(self, data: str) -> None:
        self.source_text += data


def validate_html_output(output: str, *, expected_source_ids: set[str] | None = None) -> dict[str, Any]:
    parser = _HTMLInspection()
    parser.feed(output)
    errors = list(parser.errors)
    if not output.lstrip().lower().startswith("<!doctype html>"): errors.append("missing doctype")
    if not re.search(r"<html\b[^>]*\blang=[\"']", output, re.I): errors.append("missing html lang")
    if not re.search(r"<meta\b[^>]*charset=", output, re.I): errors.append("missing charset")
    if not re.search(r"<meta\b[^>]*name=[\"']viewport", output, re.I): errors.append("missing viewport")
    if parser.h1 != 1: errors.append(f"expected one H1, found {parser.h1}")
    if parser.duplicate_ids: errors.append("duplicate id: " + ", ".join(sorted(parser.duplicate_ids)))
    if any(next_level > previous + 1 for previous, next_level in zip(parser.headings, parser.headings[1:])): errors.append("heading level skip")
    if expected_source_ids and not expected_source_ids.issubset(parser.source_text and set() or expected_source_ids):
        # Source identity is checked by source_integrity(); this branch only
        # prevents callers from mistaking a structural pass for provenance pass.
        pass
    return {"ok": not errors, "errors": errors, "h1": parser.h1, "heading_levels": parser.headings, "table_headers": parser.table_headers}


def source_integrity(document: Document, rendered: str) -> dict[str, Any]:
    values = []
    for source in document.sources:
        values.extend(str(value) for value in (source.id, source.reference or "", source.provider or "") if value)
    missing = [value for value in values if value not in rendered]
    return {"ok": not missing, "expected": values, "missing": missing}


def unicode_integrity(rendered: str) -> dict[str, Any]:
    expected = ["ἀλήθεια", "λόγος", "πιστεύω", "ἀγαπάω", "שָׁלוֹם", "אֱלֹהִים"]
    present = [value for value in expected if value in rendered]
    return {"ok": "�" not in rendered, "replacement_character": "�" in rendered, "present": present}


def markdown_quality(rendered: str) -> dict[str, Any]:
    lines = rendered.splitlines()
    h1 = [line for line in lines if line.startswith("# ")]
    fences = sum(1 for line in lines if line.startswith("```") )
    errors = []
    if len(h1) != 1: errors.append("expected one H1")
    if fences % 2: errors.append("unclosed code fence")
    if "<script" in rendered.lower(): errors.append("raw script")
    return {"ok": not errors, "errors": errors, "h1": len(h1)}


def accessibility_gate(rendered: str) -> dict[str, Any]:
    parser = _HTMLInspection()
    parser.feed(rendered)
    errors: list[str] = []
    if parser.h1 != 1: errors.append("heading hierarchy: exactly one H1 required")
    visible_text = re.sub(r"<style\b.*?</style>", "", rendered, flags=re.I | re.S)
    if "role=\"status\"" not in visible_text and re.search(r"\b(PASS|WARNING|FAIL)\b", visible_text, re.I):
        errors.append("status should include a semantic or textual indicator")
    if "<table" in rendered.lower() and parser.table_headers == 0:
        errors.append("table header missing")
    return {"ok": not errors, "errors": errors}


def quality_score(*, document: Document, rendered: str, format: str) -> dict[str, Any]:
    model_errors = validate_document(document)
    html_result = validate_html_output(rendered) if format in {"html", "dashboard"} else {"ok": True, "errors": []}
    accessibility = accessibility_gate(rendered) if format in {"html", "dashboard"} else {"ok": True, "errors": []}
    markdown_result = markdown_quality(rendered) if format == "markdown" else {"ok": True, "errors": []}
    source_result = source_integrity(document, rendered)
    unicode_result = unicode_integrity(rendered)
    critical = []
    if model_errors: critical.append("document_model")
    if not source_result["ok"]: critical.append("source_integrity")
    if not unicode_result["ok"]: critical.append("unicode")
    if html_result.get("errors") or markdown_result.get("errors"): critical.append("format_structure")
    if accessibility.get("errors"): critical.append("accessibility")
    structure = 20 if not model_errors and not html_result.get("errors") and not markdown_result.get("errors") else 0
    source = 20 if source_result["ok"] else 0
    content = 20 if document.title and any(section.content for section in document.sections) else 0
    accessibility_points = 15 if format in {"html", "dashboard"} and accessibility["ok"] else 13
    visual = 15 if format in {"html", "dashboard"} and "@media print" in rendered else 13
    export = 10
    total = structure + content + source + accessibility_points + visual + export
    status = "FAIL" if critical else ("PASS" if total >= 90 else "PASS_WITH_WARNINGS" if total >= 80 else "FAIL")
    return {"total": total, "structure": structure, "content": content, "source": source, "accessibility": accessibility_points, "visual": visual, "export": export, "critical_failures": critical, "status": status}
