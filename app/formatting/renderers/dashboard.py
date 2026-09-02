from __future__ import annotations

from .html import render_html
from ..document_model import Document


def render_dashboard(document: Document, profile: str | None = None, options: dict | None = None) -> str:
    # Keep the same safe standalone renderer and add dashboard semantics without
    # introducing a frontend framework or remote assets.
    return render_html(document, profile or "dashboard", options).replace("<main>", '<main data-page-profile="dashboard">', 1)
