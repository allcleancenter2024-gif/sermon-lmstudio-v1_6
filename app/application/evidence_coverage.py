"""Read-only citation/source/license coverage checks for canary contracts."""

from __future__ import annotations

from typing import Any

from app.application.research_contracts import EvidencePacket


def _has_value(source: dict[str, Any], *keys: str) -> bool:
    return any(str(source.get(key) or "").strip() for key in keys)


def evaluate_evidence_coverage(packet: EvidencePacket) -> dict[str, Any]:
    """Return a deterministic coverage report without changing the packet."""
    source_map = {
        str(source.get("id") or source.get("source_id")): source
        for source in packet.sources
        if source.get("id") or source.get("source_id")
    }
    referenced_ids = sorted({source_id for claim in packet.claims for source_id in claim.source_ids})
    missing_source_ids = sorted(set(referenced_ids) - set(source_map))
    referenced_sources = [source_map[source_id] for source_id in referenced_ids if source_id in source_map]
    citation_missing = sorted(
        source_id for source_id in referenced_ids if source_id in source_map and not _has_value(source_map[source_id], "citation", "reference", "source_name")
    )
    license_missing = sorted(
        source_id
        for source_id in referenced_ids
        if source_id in source_map
        and not _has_value(source_map[source_id], "license", "license_note", "license_status", "copyright_status", "attribution")
    )
    total = len(referenced_ids)
    report = {
        "ok": not missing_source_ids and not citation_missing and not license_missing,
        "claims": len(packet.claims),
        "claims_with_sources": sum(bool(claim.source_ids) for claim in packet.claims),
        "referenced_sources": total,
        "missing_source_ids": missing_source_ids,
        "citation_missing_source_ids": citation_missing,
        "license_missing_source_ids": license_missing,
        "citation_coverage": round((total - len(set(missing_source_ids) | set(citation_missing))) / total, 4) if total else 0.0,
        "license_coverage": round((total - len(set(missing_source_ids) | set(license_missing))) / total, 4) if total else 0.0,
    }
    report["status"] = "pass" if report["ok"] else "needs_review"
    return report


__all__ = ["evaluate_evidence_coverage"]
