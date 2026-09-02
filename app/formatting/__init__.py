"""Project-owned page formatting layer.

The package is deliberately independent from content generation. Legacy
V2 rendering is the default after canary validation; legacy exporters remain
available through the rollout switch and fallback paths.
"""

from .document_model import ContentBlock, Document, Section, Source, validate_document
from .format_router import render, render_to_path

__all__ = ["ContentBlock", "Document", "Section", "Source", "render", "render_to_path", "validate_document"]
