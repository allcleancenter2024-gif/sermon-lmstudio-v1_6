"""Deterministic evidence snapshot and citation trace helpers.

This additive layer does not replace the existing grounding audit.  It freezes
the evidence packet used for a generation and gives every claim/link a stable
identifier so a saved sermon version can be inspected later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re

from app.evidence import normalize_evidence
from app.grounding.audit import SermonClaim, extract_auditable_claims


@dataclass(frozen=True)
class CitationLink:
    claim_id: str
    evidence_id: str
    relation: str = "supports"
    valid: bool = True


@dataclass(frozen=True)
class EvidenceSnapshot:
    snapshot_id: str
    checksum: str
    schema_version: int
    captured_at: str
    evidence: tuple[dict, ...]


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def _evidence_rows(evidence_packet: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for item in evidence_packet:
        candidate = normalize_evidence(item)
        raw = candidate.as_dict()
        base_id = candidate.source_id or f"evidence-{_digest(raw)[:20]}"
        stable_id = base_id if base_id not in seen else f"{base_id}:{_digest(raw)[:12]}"
        if stable_id in seen:
            continue
        seen.add(stable_id)
        raw["evidence_id"] = stable_id
        raw["source_id"] = stable_id
        rows.append(raw)
    return rows


def _claim_dict(claim: SermonClaim) -> dict:
    return {
        "claim_id": claim.claim_id,
        "text": claim.text,
        "claim_type": claim.claim_type,
        "section": claim.section,
        "sentence_index": claim.sentence_index,
        "references": list(claim.references),
        "metadata": dict(claim.metadata),
    }


def _links_for_claim(claim: SermonClaim, evidence: list[dict]) -> list[CitationLink]:
    if not claim.references:
        return []
    references = {_compact(reference) for reference in claim.references}
    links = []
    for item in evidence:
        if item.get("reference") and _compact(item["reference"]) in references:
            relation = "supports" if claim.claim_type != "scripture_quote" else "quotes"
            links.append(CitationLink(claim.claim_id, str(item["evidence_id"]), relation))
    return links


def validate_citation_links(links: list[dict], evidence: list[dict]) -> dict:
    evidence_ids = {str(item.get("evidence_id")) for item in evidence if item.get("evidence_id")}
    invalid = [link for link in links if str(link.get("evidence_id")) not in evidence_ids]
    return {"ok": not invalid, "invalid_links": invalid, "evidence_count": len(evidence_ids)}


def build_evidence_trace(sermon_text: str, evidence_packet: list[dict]) -> dict:
    """Freeze packet, claims, and valid citation links for one generation."""
    evidence = _evidence_rows(list(evidence_packet or []))
    checksum = _digest(evidence)
    snapshot = EvidenceSnapshot(
        snapshot_id=f"snapshot-{checksum[:20]}",
        checksum=checksum,
        schema_version=1,
        captured_at=datetime.now(timezone.utc).isoformat(),
        evidence=tuple(evidence),
    )
    claims = [_claim_dict(claim) for claim in extract_auditable_claims(sermon_text)]
    links = []
    for claim in extract_auditable_claims(sermon_text):
        links.extend(asdict(link) for link in _links_for_claim(claim, evidence))
    validation = validate_citation_links(links, evidence)
    return {
        "snapshot": asdict(snapshot),
        "claims": claims,
        "citation_links": links,
        "validation": validation,
    }
