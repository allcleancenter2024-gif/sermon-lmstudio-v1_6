from __future__ import annotations

from typing import Any

from ..document_model import ContentBlock, Document, Section, Source


def sermon_document(*, sermon: str, meta: dict[str, Any] | None = None, sources: list[dict[str, Any]] | None = None) -> Document:
    meta = dict(meta or {})
    source_items = []
    for index, item in enumerate(sources or [], start=1):
        source_items.append(Source(
            id=str(item.get("id") or f"source-{index}"), title=item.get("translation"),
            reference=item.get("reference"), url=item.get("source_url") or item.get("url"),
            provider=item.get("provider") or item.get("translation"), citation=item.get("citation"),
            metadata=dict(item),
        ))
    blocks = [ContentBlock("paragraph", line) for line in str(sermon or "").splitlines()]
    return Document(
        document_type="sermon", title=str(meta.get("topic") or "설교문"),
        subtitle=str(meta.get("main_reference") or "") or None, metadata=meta,
        sections=[Section("sermon", "sermon", "설교 원고", blocks)], sources=source_items,
        warnings=[str(x) for x in meta.get("unchecked_references", []) if x],
    )
