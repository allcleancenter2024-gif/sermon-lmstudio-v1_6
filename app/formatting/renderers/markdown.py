from __future__ import annotations

from ..document_model import ContentBlock, Document


def _block(block: ContentBlock) -> str:
    value = block.value
    if block.type == "code":
        language = str(block.metadata.get("language") or "text")
        return f"```{language}\n{value}\n```"
    if block.type == "quote":
        return "\n".join(f"> {line}" for line in str(value).splitlines())
    if block.type == "list":
        values = value if isinstance(value, list) else [value]
        return "\n".join(f"- {item}" for item in values)
    if block.type == "warning":
        return f"> [주의] {value}"
    return str(value or "")


def render_markdown(document: Document, profile: str | None = None) -> str:
    lines = [f"# {document.title}"]
    if document.subtitle:
        lines += ["", f"{document.subtitle}"]
    for section in document.sections:
        lines += ["", f"{'#' * max(2, min(6, section.level))} {section.heading or section.id}"]
        for block in section.content:
            rendered = _block(block)
            if rendered:
                lines += ["", rendered]
    if document.sources:
        lines += ["", "## 출처"]
        for source in document.sources:
            label = source.reference or source.title or source.id
            provenance = source.provider or source.metadata.get("source_file") or ""
            lines.append(f"- [{source.id}] {label}{f' · {provenance}' if provenance else ''}")
    if document.warnings:
        lines += ["", "## 주의사항"] + [f"- {warning}" for warning in document.warnings]
    return "\n".join(lines).rstrip() + "\n"
