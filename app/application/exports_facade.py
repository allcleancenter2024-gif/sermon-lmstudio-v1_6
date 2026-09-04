"""Application boundary for approved sermon export capabilities.

The existing exporters and page-format fallback remain the implementation.
This facade only centralizes their application-facing contract; it does not
change approval, locking, integrity, or output-format behavior.
"""

from app.core import (
    DB_PATH, estimate_minutes, get_generation_audit, get_project_meta,
    get_reading_cpm, list_sermons, save_sermon, sermon_review_state,
    sermon_versions,
)
from app.exporters import dashboard_html, write_docx, write_final_package, write_pdf
from app.exporters_grounding import (
    build_grounding_report_data, render_grounding_html, render_grounding_markdown,
    safe_report_stem,
)
from app.formatting.adapters import sermon_document
from app.formatting.fallback import with_legacy_fallback
from app.formatting.format_router import page_format_v2_enabled, render, render_to_path
from app.formatting.registry import select_output
from app.formatting.rollout import v2_is_selected
from app.formatting.telemetry import record_event

__all__ = [
    "DB_PATH", "estimate_minutes", "get_generation_audit", "get_project_meta",
    "get_reading_cpm", "list_sermons", "save_sermon", "sermon_review_state",
    "sermon_versions", "dashboard_html", "write_docx", "write_final_package",
    "write_pdf", "build_grounding_report_data", "render_grounding_html",
    "render_grounding_markdown", "safe_report_stem", "sermon_document",
    "with_legacy_fallback", "page_format_v2_enabled", "render", "render_to_path",
    "select_output", "v2_is_selected", "record_event",
]
