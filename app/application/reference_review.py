"""Offline review report for reference-source readiness.

This is a preflight checker, not a web verifier.  It reports missing metadata
and catalog contract errors without claiming that a URL or license is current.
"""

from __future__ import annotations

from app.application.reference_catalog import ReferenceCatalog


def review_reference_catalog(catalog: ReferenceCatalog) -> dict[str, object]:
    """Return deterministic readiness findings without network or persistence."""
    errors = catalog.validate()
    findings: list[dict[str, str]] = []
    for error in errors:
        findings.append({"source_id": "catalog", "severity": "error", "message": error})
    for source in catalog.sources:
        if source.verification_status != "verified":
            findings.append({"source_id": source.id, "severity": "review", "message": "verification status requires review"})
        if not source.citation.strip():
            findings.append({"source_id": source.id, "severity": "review", "message": "citation is missing"})
        if not source.license_note.strip():
            findings.append({"source_id": source.id, "severity": "review", "message": "license note is missing"})
    return {
        "ready": not findings,
        "network_checked": False,
        "persistent_changes": False,
        "source_count": len(catalog.sources),
        "applyable_source_ids": [source.id for source in catalog.applyable()],
        "findings": findings,
    }


__all__ = ["review_reference_catalog"]
