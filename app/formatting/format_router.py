from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .document_model import Document, validate_document
from .profiles import resolve_profile
from .renderers import render_dashboard, render_html, render_markdown
from .quality import quality_score
from .telemetry import record_event


def page_format_v2_enabled() -> bool:
    return os.getenv("PAGE_FORMAT_V2", "true").strip().lower() in {"1", "true", "yes", "on"}


def render(document: Document, format: str, profile: str | None = None, options: dict[str, Any] | None = None) -> str:
    started = time.perf_counter()
    record_event("render_started", format=format, profile=profile or document.document_type)
    errors = validate_document(document)
    if errors:
        record_event("quality_gate_failed", format=format, profile=profile or document.document_type, status="failed", error_code="PF_DOC_INVALID")
        raise ValueError("문서 모델 검증 실패: " + "; ".join(errors))
    fmt = format.strip().lower()
    resolved = resolve_profile(document.document_type, profile).name
    try:
        if fmt == "markdown":
            output = render_markdown(document, resolved)
        elif fmt == "html":
            output = render_html(document, resolved, options)
        elif fmt == "dashboard":
            output = render_dashboard(document, resolved, options)
        else:
            record_event("render_failed", format=fmt, profile=resolved, status="failed", error_code="PF_TEMPLATE_ERROR")
            raise ValueError(f"지원하지 않는 page format: {format}")
        score = quality_score(document=document, rendered=output, format=fmt)
        record_event("render_completed", format=fmt, profile=resolved, duration_ms=round((time.perf_counter() - started) * 1000), output_size=len(output.encode("utf-8")), status=score["status"], quality_score=score["total"])
        return output
    except ValueError:
        raise
    except Exception:
        record_event("render_failed", format=fmt, profile=resolved, status="failed", error_code="PF_TEMPLATE_ERROR")
        raise


def render_to_path(document: Document, format: str, path: Path, profile: str | None = None, options: dict[str, Any] | None = None) -> Path:
    fmt = format.strip().lower()
    if fmt in {"markdown", "html", "dashboard"}:
        suffix = ".md" if fmt == "markdown" else ".html"
        path.write_text(render(document, fmt, profile, options), encoding="utf-8")
        return path
    # Adapters reuse the existing production exporters. Local imports avoid a
    # circular dependency and keep legacy export behavior unchanged by default.
    from app.exporters import write_docx, write_pdf
    meta = dict(document.metadata)
    sermon = "\n".join(str(block.value) for section in document.sections for block in section.content)
    if fmt == "docx":
        write_docx(path, sermon=sermon, meta=meta)
    elif fmt == "pdf":
        write_pdf(path, sermon=sermon, meta=meta, sources=[source.metadata for source in document.sources])
    else:
        raise ValueError(f"지원하지 않는 page format: {format}")
    return path
