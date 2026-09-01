from __future__ import annotations

import os

from app.evidence.models import EvidenceCandidate
from app.repositories.bible import compare_reference

from .models import GroundingContext, GroundingDecision


def validator_enabled() -> bool:
    return os.getenv("GROUNDING_VALIDATOR_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _registered_scripture(candidate: EvidenceCandidate, context: GroundingContext) -> bool:
    if not candidate.reference:
        return False
    try:
        rows = compare_reference(candidate.reference, context.db_path) if context.db_path is not None else compare_reference(candidate.reference)
    except (ValueError, TypeError, OSError):
        return False
    if not rows or not candidate.text.strip():
        return False
    if candidate.source_name:
        return any(str(row.get("translation", "")).strip() == str(candidate.source_name).strip() for row in rows)
    return True


def validate_evidence(candidate: EvidenceCandidate, context: GroundingContext | None = None) -> GroundingDecision:
    context = context or GroundingContext()
    source_type = candidate.source_type
    if context.allowed_source_types is not None and source_type not in context.allowed_source_types:
        return GroundingDecision("X", "rejected", "허용되지 않은 source_type입니다.")
    if source_type == "scripture":
        if _registered_scripture(candidate, context):
            return GroundingDecision("A", "approved", "등록된 성경 본문과 출처가 확인되었습니다.", 1.0)
        return GroundingDecision("X", "rejected", "성경 reference가 DB에 등록되지 않았거나 본문/번역본이 없습니다.", 1.0)
    if source_type == "original_language":
        if candidate.reference and candidate.text.strip() and (candidate.metadata.get("lemma") or candidate.metadata.get("morphology")):
            return GroundingDecision("A", "approved", "등록된 원어 reference와 lemma/morphology가 확인되었습니다.", 0.9)
        return GroundingDecision("X", "rejected", "원어 자료의 reference 또는 lemma/morphology가 확인되지 않았습니다.", 0.9)
    if source_type in {"translation", "doctrine"}:
        if candidate.source_name and candidate.text.strip():
            return GroundingDecision("B", "approved", "등록된 보조 근거의 출처와 본문이 확인되었습니다.", 0.8)
        return GroundingDecision("B", "weak", "보조 근거의 출처 metadata가 불완전합니다.", 0.5)
    if source_type in {"commentary", "user_material", "notebook"}:
        status = "weak" if context.strictness != "strict" else "rejected"
        return GroundingDecision("C", status, "보조 연구자료로 분류되며 성경/교리 근거로 승격하지 않습니다.", 0.6)
    if source_type == "web":
        return GroundingDecision("D", "weak", "웹 자료는 별도 검증 전 보조 자료로만 취급합니다.", 0.4)
    return GroundingDecision("X", "rejected", "출처 유형 또는 출처 identity를 확인할 수 없습니다.", 0.0)


def filter_evidence(candidates: list[EvidenceCandidate], context: GroundingContext | None = None) -> tuple[list[EvidenceCandidate], list[GroundingDecision]]:
    context = context or GroundingContext()
    kept, decisions = [], []
    for candidate in candidates:
        decision = validate_evidence(candidate, context)
        decisions.append(decision)
        if decision.status == "approved" or (decision.status == "weak" and context.strictness != "strict"):
            kept.append(candidate)
    return kept, decisions
