"""Application boundary for sermon version review and audit workflows.

The existing repository-backed implementations remain unchanged.  This
facade centralizes the application contract used by HTTP endpoints so review,
reaudit, and final-lock gates cannot be bypassed by a new import path.
"""

from app.core import (
    add_sermon_review,
    apply_revision_suggestions,
    compare_sermon_versions,
    generate_revision_suggestions,
    get_generation_audit,
    lock_sermon_version,
    reaudit_sermon_version,
    revision_suggestions,
    save_sermon,
    sermon_review_state,
    sermon_versions,
)

__all__ = [
    "add_sermon_review", "apply_revision_suggestions", "compare_sermon_versions",
    "generate_revision_suggestions", "get_generation_audit", "lock_sermon_version",
    "reaudit_sermon_version", "revision_suggestions", "save_sermon",
    "sermon_review_state", "sermon_versions",
]
