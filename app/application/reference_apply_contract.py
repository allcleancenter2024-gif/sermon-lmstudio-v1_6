"""Dry-run contract for applying a verified reference source.

The contract deliberately produces a plan only.  It never writes to SQLite,
project files, Bible data, backups, or external services.  A later mutation
boundary must consume this plan only after backup and explicit user approval.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.reference_catalog import ReferenceCatalog


@dataclass(frozen=True)
class ReferenceApplyPlan:
    requested_source_ids: tuple[str, ...]
    approved_source_ids: tuple[str, ...]
    rejected_source_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    dry_run: bool = True
    requires_backup: bool = True
    mutates_data: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "requested_source_ids": list(self.requested_source_ids),
            "approved_source_ids": list(self.approved_source_ids),
            "rejected_source_ids": list(self.rejected_source_ids),
            "reasons": list(self.reasons),
            "dry_run": self.dry_run,
            "requires_backup": self.requires_backup,
            "mutates_data": self.mutates_data,
        }


def build_reference_apply_plan(
    catalog: ReferenceCatalog,
    source_ids: tuple[str, ...] | list[str],
    *,
    user_approved: bool = False,
) -> ReferenceApplyPlan:
    """Return an immutable, non-mutating plan for a future apply operation."""
    requested = tuple(dict.fromkeys(str(source_id).strip() for source_id in source_ids if str(source_id).strip()))
    approved: list[str] = []
    rejected: list[str] = []
    reasons: list[str] = []
    catalog_errors = catalog.validate()
    if catalog_errors:
        return ReferenceApplyPlan(requested, (), requested, tuple(catalog_errors), mutates_data=False)
    for source_id in requested:
        source = catalog.get(source_id)
        if source is None:
            rejected.append(source_id)
            reasons.append(f"{source_id}: source not found")
        elif not source.can_apply():
            rejected.append(source_id)
            reasons.append(f"{source_id}: source is not verified and applyable")
        elif not user_approved:
            rejected.append(source_id)
            reasons.append(f"{source_id}: explicit user approval is required")
        else:
            approved.append(source_id)
    return ReferenceApplyPlan(requested, tuple(approved), tuple(rejected), tuple(reasons))


__all__ = ["ReferenceApplyPlan", "build_reference_apply_plan"]
