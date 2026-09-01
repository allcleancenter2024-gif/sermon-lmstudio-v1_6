from __future__ import annotations

from .models import EvidenceCandidate


def _source_type(row: dict) -> str:
    value = str(row.get("source_type") or "").strip().lower()
    if value in {"scripture", "original_language", "translation", "doctrine", "commentary", "user_material", "notebook", "web"}:
        return value
    if row.get("lemma") or row.get("morphology"):
        return "original_language"
    if row.get("tradition") or row.get("title") and row.get("text") and row.get("source_url"):
        return "doctrine"
    if row.get("source_type") == "notebooklm":
        return "notebook"
    if row.get("translation") and row.get("reference"):
        return "scripture"
    return "unknown"


def normalize_evidence(row: dict, *, source_type: str | None = None) -> EvidenceCandidate:
    row = dict(row or {})
    metadata = dict(row)
    return EvidenceCandidate(
        source_id=str(row.get("source_id", row.get("id"))) if row.get("source_id", row.get("id")) is not None else None,
        source_type=source_type or _source_type(row),
        source_name=row.get("source_name") or row.get("translation") or row.get("source"),
        reference=row.get("reference"),
        text=str(row.get("text") or ""),
        page=row.get("page"),
        chunk_id=str(row["chunk_id"]) if row.get("chunk_id") is not None else None,
        retrieval_type=row.get("retrieval_type"),
        semantic_rank=row.get("semantic_rank"),
        lexical_rank=row.get("lexical_rank"),
        rrf_score=row.get("rrf_score"),
        metadata=metadata,
    )


def dedupe_evidence(candidates: list[EvidenceCandidate]) -> list[EvidenceCandidate]:
    seen: set[tuple] = set()
    result = []
    for candidate in candidates:
        key = ((candidate.source_id,) if candidate.source_id else (candidate.reference, candidate.source_name, candidate.chunk_id))
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result
