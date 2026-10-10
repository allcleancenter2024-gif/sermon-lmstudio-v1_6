"""Pure Gate 1 contracts for research-section persistence and snapshots.

The contracts describe the data that a later migration may persist.  This
module intentionally does not import SQLite, FastAPI, providers, repositories,
or renderers and does not execute schema changes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar


PERSISTENCE_SCHEMA_VERSION = 1
SECTION_STATUSES = frozenset(
    {
        "not_generated",
        "generating",
        "ready",
        "insufficient_evidence",
        "needs_review",
        "approved",
        "failed",
    }
)
QUALITY_STATUSES = frozenset({"not_checked", "passed", "warning", "failed"})
REVIEW_STATUSES = frozenset({"unreviewed", "in_review", "changes_requested", "approved"})


@dataclass(frozen=True)
class ResearchSectionRecord:
    """Versioned section payload proposed for the Canary persistence gate."""

    project_id: int
    section_type: str
    version: int
    status: str
    content: dict[str, Any]
    source_coverage: float = 0.0
    quality_status: str = "not_checked"
    review_status: str = "unreviewed"
    source_snapshot_id: str = ""

    schema_version: ClassVar[int] = PERSISTENCE_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.project_id <= 0:
            errors.append("project_id must be positive")
        if not self.section_type.strip():
            errors.append("section_type is required")
        if self.version <= 0:
            errors.append("version must be positive")
        if self.status not in SECTION_STATUSES:
            errors.append(f"unsupported section status: {self.status}")
        if self.quality_status not in QUALITY_STATUSES:
            errors.append(f"unsupported quality status: {self.quality_status}")
        if self.review_status not in REVIEW_STATUSES:
            errors.append(f"unsupported review status: {self.review_status}")
        if not 0 <= self.source_coverage <= 1:
            errors.append("source_coverage must be between 0 and 1")
        if self.status in {"ready", "approved"} and not self.content:
            errors.append(f"{self.status} section requires content")
        if self.review_status == "approved" and self.status != "approved":
            errors.append("approved review requires approved section status")
        return errors

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = self.schema_version
        return data


@dataclass(frozen=True)
class RenderSnapshot:
    """Immutable identifiers needed to reproduce one approved output."""

    project_id: int
    research_version: int
    language_version: int
    sermon_version: int
    evidence_version: int
    renderer_version: str
    section_versions: tuple[tuple[str, int], ...]
    output_profile: dict[str, Any]
    created_at: str

    schema_version: ClassVar[int] = PERSISTENCE_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.project_id <= 0:
            errors.append("project_id must be positive")
        for name in ("research_version", "language_version", "sermon_version", "evidence_version"):
            if getattr(self, name) <= 0:
                errors.append(f"{name} must be positive")
        if not self.renderer_version.strip():
            errors.append("renderer_version is required")
        if not self.created_at.strip():
            errors.append("created_at is required")
        section_ids = [section_id for section_id, _ in self.section_versions]
        if len(section_ids) != len(set(section_ids)):
            errors.append("section_versions must contain unique section ids")
        if any(not section_id.strip() or version <= 0 for section_id, version in self.section_versions):
            errors.append("section_versions requires non-empty ids and positive versions")
        if not self.output_profile:
            errors.append("output_profile is required")
        return errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "research_version": self.research_version,
            "language_version": self.language_version,
            "sermon_version": self.sermon_version,
            "evidence_version": self.evidence_version,
            "renderer_version": self.renderer_version,
            "section_versions": dict(self.section_versions),
            "output_profile": dict(self.output_profile),
            "created_at": self.created_at,
        }


PROPOSED_TABLES = (
    "sermon_research_packages",
    "sermon_sections",
    "sermon_claims",
    "sermon_evidence_links",
    "sermon_assets",
    "sermon_render_snapshots",
    "sermon_review_events",
)


__all__ = [
    "PERSISTENCE_SCHEMA_VERSION",
    "PROPOSED_TABLES",
    "QUALITY_STATUSES",
    "REVIEW_STATUSES",
    "SECTION_STATUSES",
    "RenderSnapshot",
    "ResearchSectionRecord",
]
