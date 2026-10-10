"""Non-persistent contracts for the next research-package canary.

This module deliberately contains only typed application data.  It does not
import the database, FastAPI, providers, or renderers and does not create a
new SQLite schema.  Persistence and HTTP integration require a later gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar


CONTRACT_SCHEMA_VERSION = 1
VERIFICATION_STATUSES = frozenset(
    {"verified", "partially_verified", "needs_review", "conflicting", "unsupported"}
)
OUTPUT_FORMATS = frozenset({"sermon", "research_book", "small_group", "hymn_guide", "html", "markdown", "pdf"})


def _copy_mapping(value: dict[str, Any] | None) -> dict[str, Any]:
    return dict(value or {})


@dataclass(frozen=True)
class ResearchPackage:
    """Structured research data without persistence or generation behavior."""

    passage_structure: dict[str, Any] = field(default_factory=dict)
    historical_context: dict[str, Any] = field(default_factory=dict)
    cultural_context: dict[str, Any] = field(default_factory=dict)
    cross_references: tuple[dict[str, Any], ...] = ()
    patristic_tradition: tuple[dict[str, Any], ...] = ()
    preaching_tradition: tuple[dict[str, Any], ...] = ()
    scholarship: tuple[dict[str, Any], ...] = ()
    maps: tuple[dict[str, Any], ...] = ()
    artworks: tuple[dict[str, Any], ...] = ()

    schema_version: ClassVar[int] = CONTRACT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = self.schema_version
        return data


@dataclass(frozen=True)
class LanguagePackage:
    """Original-language and translation data kept separate from application."""

    translations: tuple[dict[str, Any], ...] = ()
    keywords: tuple[dict[str, Any], ...] = ()
    morphology: tuple[dict[str, Any], ...] = ()
    interlinear: tuple[dict[str, Any], ...] = ()
    verse_language_notes: tuple[dict[str, Any], ...] = ()

    schema_version: ClassVar[int] = CONTRACT_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["schema_version"] = self.schema_version
        return data


@dataclass(frozen=True)
class EvidenceClaim:
    id: str
    section_id: str
    statement: str
    claim_type: str
    source_ids: tuple[str, ...] = ()
    viewpoint: str | None = None
    confidence: float | None = None
    verification_status: str = "needs_review"

    def validate(self) -> list[str]:
        errors: list[str] = []
        for name in ("id", "section_id", "statement", "claim_type"):
            if not getattr(self, name).strip():
                errors.append(f"{name} is required")
        if self.verification_status not in VERIFICATION_STATUSES:
            errors.append(f"unsupported verification_status: {self.verification_status}")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            errors.append("confidence must be between 0 and 1")
        return errors

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidencePacket:
    claims: tuple[EvidenceClaim, ...] = ()
    evidence: tuple[dict[str, Any], ...] = ()
    sources: tuple[dict[str, Any], ...] = ()
    conflicts: tuple[dict[str, Any], ...] = ()
    confidence: float | None = None

    schema_version: ClassVar[int] = CONTRACT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors = [error for claim in self.claims for error in claim.validate()]
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            errors.append("packet confidence must be between 0 and 1")
        source_ids = {
            str(source.get("id") or source.get("source_id"))
            for source in self.sources
            if source.get("id") or source.get("source_id")
        }
        for claim in self.claims:
            missing = [source_id for source_id in claim.source_ids if source_id not in source_ids]
            if missing:
                errors.append(f"claim {claim.id} references missing sources: {', '.join(missing)}")
        return errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "claims": [claim.as_dict() for claim in self.claims],
            "evidence": [dict(item) for item in self.evidence],
            "sources": [dict(item) for item in self.sources],
            "conflicts": [dict(item) for item in self.conflicts],
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class OutputProfile:
    """Allowed output selections; it does not invoke any renderer."""

    enabled_formats: tuple[str, ...] = ("sermon", "html", "markdown", "pdf")
    section_ids: tuple[str, ...] = ()

    schema_version: ClassVar[int] = CONTRACT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        return [f"unsupported output format: {item}" for item in self.enabled_formats if item not in OUTPUT_FORMATS]

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "enabled_formats": list(self.enabled_formats), "section_ids": list(self.section_ids)}


def validate_contracts(
    research: ResearchPackage,
    language: LanguagePackage,
    evidence: EvidencePacket,
    output: OutputProfile,
) -> dict[str, list[str]]:
    """Validate the Gate 1 payloads without persistence or side effects."""
    return {"research": [], "language": [], "evidence": evidence.validate(), "output": output.validate()}


__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "EvidenceClaim",
    "EvidencePacket",
    "LanguagePackage",
    "OutputProfile",
    "ResearchPackage",
    "validate_contracts",
]
