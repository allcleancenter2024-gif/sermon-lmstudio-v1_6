"""Pure contract for user-visible reference sources.

The catalog is intentionally non-persistent and offline.  It provides the
safe boundary needed by a future ``[관련자료참고]`` screen without making
network requests, changing the database, or applying external content.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse


VERIFICATION_STATUSES = frozenset({"unverified", "needs_review", "verified", "blocked"})


@dataclass(frozen=True)
class ReferenceSource:
    """A source candidate with explicit provenance and application policy."""

    id: str
    label: str
    category: str
    url: str
    citation: str = ""
    license_note: str = ""
    verification_status: str = "unverified"
    allowed_for_application: bool = False

    def validate(self, allowed_domains: tuple[str, ...] = ()) -> list[str]:
        errors: list[str] = []
        for name in ("id", "label", "category", "url"):
            if not getattr(self, name).strip():
                errors.append(f"{name} is required")
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("url must use http or https")
        if allowed_domains and parsed.hostname not in set(allowed_domains):
            errors.append("url domain is not in the catalog allowlist")
        if self.verification_status not in VERIFICATION_STATUSES:
            errors.append(f"unsupported verification_status: {self.verification_status}")
        if self.allowed_for_application:
            if self.verification_status != "verified":
                errors.append("application requires verified source")
            if not self.citation.strip():
                errors.append("application requires citation")
            if not self.license_note.strip():
                errors.append("application requires license_note")
        if self.verification_status == "blocked" and self.allowed_for_application:
            errors.append("blocked source cannot be applied")
        return errors

    def can_apply(self) -> bool:
        return (
            self.allowed_for_application
            and self.verification_status == "verified"
            and bool(self.citation.strip())
            and bool(self.license_note.strip())
        )

    def as_dict(self) -> dict[str, object]:
        return asdict(self) | {"can_apply": self.can_apply()}


@dataclass(frozen=True)
class ReferenceCatalog:
    """Immutable source registry; validation has no external side effects."""

    sources: tuple[ReferenceSource, ...] = ()
    allowed_domains: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        errors: list[str] = []
        ids = [source.id for source in self.sources]
        if len(ids) != len(set(ids)):
            errors.append("source id must be unique")
        for source in self.sources:
            errors.extend(f"{source.id}: {error}" for error in source.validate(self.allowed_domains))
        return errors

    def get(self, source_id: str) -> ReferenceSource | None:
        return next((source for source in self.sources if source.id == source_id), None)

    def applyable(self) -> tuple[ReferenceSource, ...]:
        return tuple(source for source in self.sources if source.can_apply())

    def as_dict(self) -> dict[str, object]:
        return {
            "allowed_domains": list(self.allowed_domains),
            "sources": [source.as_dict() for source in self.sources],
        }


__all__ = ["ReferenceCatalog", "ReferenceSource", "VERIFICATION_STATUSES"]
