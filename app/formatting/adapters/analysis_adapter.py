from __future__ import annotations

from typing import Any

from ..document_model import ContentBlock, Document, Section, Source


def analysis_document(*, title: str, items: list[dict[str, Any]] | None = None, metadata: dict[str, Any] | None = None) -> Document:
    items = items or []
    blocks = [ContentBlock("greek_analysis", item, metadata={"source": item.get("source", {})}) for item in items]
    sources = [Source(id=f"analysis-source-{i}", reference=item.get("reference"), provider=item.get("source", {}).get("version"), metadata=dict(item.get("source", {}))) for i, item in enumerate(items, 1)]
    return Document("analysis", title, metadata=dict(metadata or {}), sections=[Section("analysis", "analysis", "분석 결과", blocks)], sources=sources)
