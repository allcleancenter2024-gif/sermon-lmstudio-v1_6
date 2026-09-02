from __future__ import annotations

from typing import Any

from ..document_model import ContentBlock, Document, Section


def report_document(*, title: str, summary: str, sections: list[dict[str, Any]] | None = None, warnings: list[str] | None = None) -> Document:
    mapped = [Section(str(item.get("id") or f"section-{i}"), str(item.get("type") or "report"), item.get("heading"), [ContentBlock("paragraph", item.get("content", ""))], int(item.get("level") or 2)) for i, item in enumerate(sections or [], 1)]
    if not mapped:
        mapped = [Section("summary", "report", "요약", [ContentBlock("paragraph", summary)])]
    return Document("report", title, metadata={"summary": summary}, sections=mapped, warnings=list(warnings or []))
