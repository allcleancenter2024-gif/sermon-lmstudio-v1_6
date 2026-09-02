from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeVar

from .telemetry import record_event

T = TypeVar("T")


def legacy_fallback_enabled() -> bool:
    return os.getenv("ALLOW_LEGACY_FALLBACK", "true").strip().lower() in {"1", "true", "yes", "on"}


def with_legacy_fallback(*, format: str, profile: str, theme: str | None, preset: str | None, render_v2: Callable[[], T], render_legacy: Callable[[], T]) -> T:
    try:
        return render_v2()
    except ValueError:
        # Validation and unsupported-format errors are explicit failures. They
        # must never be disguised as a successful legacy export.
        raise
    except Exception:
        if not legacy_fallback_enabled():
            raise
        code = {"html": "PF_FALLBACK_HTML_RENDER", "pdf": "PF_FALLBACK_PDF_EXPORT", "docx": "PF_FALLBACK_DOCX_EXPORT"}.get(format, "PF_FALLBACK_PROFILE_UNSUPPORTED")
        record_event("fallback_used", format=format, profile=profile, theme=theme, preset=preset, status="fallback", error_code=code)
        return render_legacy()
