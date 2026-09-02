from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContentBlock:
    type: str
    value: Any = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Section:
    id: str
    type: str
    heading: str | None = None
    content: list[ContentBlock] = field(default_factory=list)
    level: int = 2


@dataclass
class Source:
    id: str
    title: str | None = None
    reference: str | None = None
    url: str | None = None
    provider: str | None = None
    citation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    document_type: str
    title: str
    subtitle: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[Section] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_document(document: Document) -> list[str]:
    errors: list[str] = []
    if not isinstance(document.title, str) or not document.title.strip():
        errors.append("title is required")
    if not isinstance(document.document_type, str) or not document.document_type.strip():
        errors.append("document_type is required")
    seen_sections: set[str] = set()
    for section in document.sections:
        if not section.id.strip():
            errors.append("section id is required")
        if section.id in seen_sections:
            errors.append(f"duplicate section id: {section.id}")
        seen_sections.add(section.id)
        if section.level < 1 or section.level > 6:
            errors.append(f"invalid section level: {section.id}")
        for block in section.content:
            if block.type not in {"paragraph", "heading", "quote", "list", "table", "code", "metric", "callout", "timeline", "comparison", "greek_analysis", "source", "warning"}:
                errors.append(f"unsupported content block: {block.type}")
    seen_sources: set[str] = set()
    for source in document.sources:
        if not source.id.strip():
            errors.append("source id is required")
        if source.id in seen_sources:
            errors.append(f"duplicate source id: {source.id}")
        seen_sources.add(source.id)
    return errors
