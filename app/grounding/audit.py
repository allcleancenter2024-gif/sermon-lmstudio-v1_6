from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.constants import DIRECT_QUOTE_RE, EVIDENCE_CUE_RE, ORIGINAL_CUE_RE, DOCTRINE_CUE_RE, REFERENCE_RE
from app.evidence import normalize_evidence


@dataclass
class SermonClaim:
    claim_id: str
    text: str
    claim_type: str
    section: str | None = None
    sentence_index: int | None = None
    references: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class GroundingAuditResult:
    claim_id: str
    status: str
    matched_evidence_ids: list[str]
    reason: str
    source_tiers: list[str]


@dataclass
class GroundingAuditReport:
    total_claims: int
    auditable_claims: int
    grounded: int
    partially_grounded: int
    ungrounded: int
    grounding_coverage: float
    results: list[GroundingAuditResult]
    status: str = "completed"
    elapsed_ms: float | None = None

    def as_dict(self) -> dict:
        return {"total_claims": self.total_claims, "auditable_claims": self.auditable_claims,
                "grounded": self.grounded, "partially_grounded": self.partially_grounded,
                "ungrounded": self.ungrounded, "grounding_coverage": self.grounding_coverage,
                "status": self.status, "elapsed_ms": self.elapsed_ms,
                "results": [r.__dict__ for r in self.results]}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+|\n+", text or "") if s.strip()]


def extract_auditable_claims(sermon_text: str) -> list[SermonClaim]:
    claims = []
    for index, sentence in enumerate(_sentences(sermon_text), 1):
        refs = [a or b for a, b in REFERENCE_RE.findall(sentence)] if REFERENCE_RE.groups == 2 else REFERENCE_RE.findall(sentence)
        refs = [str(r) for r in refs]
        quote = bool(DIRECT_QUOTE_RE.search(sentence))
        if quote and refs:
            claim_type = "scripture_quote"
        elif ORIGINAL_CUE_RE.search(sentence):
            claim_type = "original_language_claim"
        elif refs or EVIDENCE_CUE_RE.search(sentence):
            claim_type = "scripture_claim"
        elif DOCTRINE_CUE_RE.search(sentence):
            claim_type = "doctrine_claim"
        elif re.search(r"\d+(?:\.\d+)?\s*(?:%|퍼센트|명|억|만 명)|통계|조사에 따르면|연구에 따르면", sentence):
            claim_type = "statistical_claim"
        elif re.search(r"1세기|로마 제국|초대교회|역사적으로", sentence):
            claim_type = "historical_claim"
        elif re.search(r"최근|현재 국제|경제|정세|뉴스에 따르면", sentence):
            claim_type = "external_fact"
        elif re.search(r"하십시오|하세요|합시다|해 보", sentence):
            claim_type = "application_statement"
        else:
            continue
        claims.append(SermonClaim(f"claim-{index}", sentence, claim_type, sentence_index=index, references=refs))
    return claims


def audit_claim(claim: SermonClaim, evidence_packet: list[dict]) -> GroundingAuditResult:
    candidates = [normalize_evidence(item) for item in evidence_packet]
    if claim.claim_type in {"application_statement", "general_statement"}:
        return GroundingAuditResult(claim.claim_id, "not_applicable", [], "적용/일반 문장은 감사 대상이 아닙니다.", [])
    matched = []
    for candidate in candidates:
        if claim.references and candidate.reference and any(re.sub(r"\s+", "", r) == re.sub(r"\s+", "", candidate.reference) for r in claim.references):
            matched.append(candidate)
    if claim.claim_type == "scripture_quote" and matched:
        quotes = [a or b for a, b in DIRECT_QUOTE_RE.findall(claim.text)]
        compact = [re.sub(r"[\s\W_]", "", q, flags=re.UNICODE) for q in quotes]
        texts = [re.sub(r"[\s\W_]", "", c.text, flags=re.UNICODE) for c in matched]
        if compact and all(any(q in t for t in texts) for q in compact):
            return GroundingAuditResult(claim.claim_id, "grounded", [c.source_id for c in matched if c.source_id], "직접 인용이 등록 Evidence와 일치합니다.", ["A" if c.source_type in {"scripture", "original_language"} else "B" for c in matched])
        return GroundingAuditResult(claim.claim_id, "partially_grounded", [c.source_id for c in matched if c.source_id], "reference는 확인되지만 직접 인용 일부가 불일치합니다.", ["A" if c.source_type in {"scripture", "original_language"} else "B" for c in matched])
    if claim.claim_type in {"scripture_claim", "original_language_claim", "doctrine_claim"}:
        if matched:
            return GroundingAuditResult(claim.claim_id, "grounded", [c.source_id for c in matched if c.source_id], "명시 reference와 Evidence가 연결됩니다.", ["A" if c.source_type in {"scripture", "original_language"} else "B" for c in matched])
        return GroundingAuditResult(claim.claim_id, "ungrounded", [], "명시 reference 또는 해당 Evidence가 없습니다.", [])
    if claim.claim_type in {"statistical_claim", "historical_claim", "external_fact"}:
        return GroundingAuditResult(claim.claim_id, "grounded" if matched else "ungrounded", [c.source_id for c in matched if c.source_id], "외부 자료 Evidence가 확인되었습니다." if matched else "외부 사실의 출처 Evidence가 없습니다.", ["C" if c.source_type in {"commentary", "user_material", "notebook"} else "D" for c in matched])
    return GroundingAuditResult(claim.claim_id, "not_applicable", [], "감사 대상이 아닌 일반 문장입니다.", [])


def audit_sermon(sermon_text: str, evidence_packet: list[dict]) -> GroundingAuditReport:
    claims = extract_auditable_claims(sermon_text)
    results = [audit_claim(claim, evidence_packet) for claim in claims]
    auditable = [r for r in results if r.status != "not_applicable"]
    grounded = sum(r.status == "grounded" for r in auditable)
    partial = sum(r.status == "partially_grounded" for r in auditable)
    ungrounded = sum(r.status == "ungrounded" for r in auditable)
    return GroundingAuditReport(len(claims), len(auditable), grounded, partial, ungrounded,
                                round(grounded / len(auditable), 4) if auditable else 1.0, results)
