"""Pure input/output contracts for section-level canary regeneration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

from app.application.section_registry import CANARY_SECTION_IDS, SectionBuildResult


@dataclass(frozen=True)
class SectionRegenerationRequest:
    section_id: str
    context: dict[str, Any]
    evidence: dict[str, Any]
    source_snapshot_id: str = ""
    attempt: int = 0

    def validate(self, known_ids: tuple[str, ...] = CANARY_SECTION_IDS) -> list[str]:
        errors: list[str] = []
        if self.section_id not in known_ids:
            errors.append(f"unsupported section: {self.section_id}")
        if self.attempt < 0:
            errors.append("attempt must be zero or greater")
        if not isinstance(self.context, dict):
            errors.append("context must be a mapping")
        if not isinstance(self.evidence, dict):
            errors.append("evidence must be a mapping")
        return errors

    def retry(self) -> "SectionRegenerationRequest":
        return replace(self, attempt=self.attempt + 1)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_section_result(result: SectionBuildResult) -> list[str]:
    """Validate a builder result without changing its status or payload."""
    errors: list[str] = []
    if result.status not in {"ready", "failed", "invalid", "unregistered", "disabled"}:
        errors.append(f"unsupported section status: {result.status}")
    if result.status == "ready" and not isinstance(result.render_data, dict):
        errors.append("ready section must have render_data")
    if result.status in {"failed", "invalid", "unregistered"} and not result.errors:
        errors.append(f"{result.status} section must include errors")
    return errors


__all__ = ["SectionRegenerationRequest", "validate_section_result"]
