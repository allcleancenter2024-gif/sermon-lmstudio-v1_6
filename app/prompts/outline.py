"""Outline prompt construction with explicit application-service dependencies."""

from __future__ import annotations

import json
from app.prompts.contracts import (
    CompactOutlineStudy,
    GroundingBuilder,
    InterpretationFlowPrompt,
    PassageSorter,
    SocialContextPolicyPrompt,
    TranslationPolicyPrompt,
)


def build_outline_prompt(
    payload: dict,
    study: dict,
    time_plan: dict,
    *,
    compact_outline_study: CompactOutlineStudy,
    sort_interpretation_passages: PassageSorter,
    build_grounding: GroundingBuilder,
    build_interpretation_flow_prompt: InterpretationFlowPrompt,
    build_translation_policy_prompt: TranslationPolicyPrompt,
    build_social_context_policy_prompt: SocialContextPolicyPrompt,
) -> tuple[str, str]:
    """Build the JSON-only outline prompt without importing ``app.core``."""
    study = compact_outline_study(study)
    evidence = sort_interpretation_passages(
        (study.get("translations") or []) + (study.get("context") or [])
    )
    allowed_refs = sorted({str(x.get("reference", "")).strip() for x in evidence if x.get("reference")})
    originals = study.get("original_notes") or []
    original_block = "\n".join(
        f"[{n.get('reference','')} | {n.get('language','')}] {n.get('lemma','')} / "
        f"뜻: {str(n.get('gloss',''))[:60]} / 형태: {str(n.get('morphology',''))[:60]} / "
        f"출처: {str(n.get('source',''))[:60]} / 사용조건: {str(n.get('license_note',''))[:60]} / "
        f"뜻출처: {str(n.get('lexicon_source',''))[:60]} / 뜻사용조건: {str(n.get('lexicon_license_note',''))[:60]}"
        for n in originals
    ) or "등록 원어 근거 없음"
    system = """당신은 목회자의 설교 구조 작성을 돕는 편집자입니다.
제공된 등록 성경/원어 근거만 사용하십시오. 기억으로 새 구절, 원어 뜻, 역사 사실을 추가하지 마십시오.
해석은 개역개정 → 히브리어/헬라어 원문 → ESV/NASB → NIV/CSB → NET 번역주석 → NLT 쉬운 표현 → 주석·신앙고백 문서 순서를 따르십시오.
단, 등록되지 않은 단계는 기억으로 보충하지 말고 건너뛰며, 번역 표현을 단순 나열하지 말고 차이의 의미를 핵심 메시지와 세 대지에 종합하십시오.
ESV·NASB·NIV·CSB·NET을 핵심 비교에 우선하고 NRSVue·NKJV·NLT는 연구 확장, KJV·GNT·CEV·AMP·The Message는 비교·교육 보조로만 사용하십시오.
AMP와 The Message는 표현을 이해하는 데만 사용하고 원어 의미나 교리적 결론의 증거로 사용하지 마십시오.
ESV/NASB는 문장 구조와 핵심어를 발견하는 단서이며 원래 의미의 최종 증거가 아닙니다. 원어 주장은 등록 히브리어/헬라어로 확인하십시오.
NIV/NLT는 현대적 문장과 적용 표현에, The Message는 생동감 있는 표현 아이디어에만 사용하십시오.
시대 적용은 정당·정치인·이념을 편들지 말고 공의·사랑·화해·책임을 모든 진영에 동일하게 적용하십시오.
구체적인 2026년 사건·수치·발언은 사용자 세부사항이나 등록 근거가 없으면 만들지 말고, 국제 사건을 하나님의 심판·예언 성취로 단정하지 마십시오.
세 대지는 서로 겹치지 않게 구성하고 각 대지의 reference는 반드시 허용 참조 중 하나만 사용하십시오.
illustration_direction은 검증되지 않은 실화가 아니라 '사용할 수 있는 예화의 방향'만 제안하십시오.
반드시 JSON 객체 하나만 출력하십시오."""
    user = f"""[설교 요청]
주제: {str(payload.get('topic', '')).strip()}
세부사항: {str(payload.get('details', '')).strip()[:600]}
중심본문: {str(payload.get('main_reference', '')).strip()}
청중: {payload.get('audience', '전 연령')}
신학적 전통: {payload.get('tradition', '초교파 복음주의')}

[정확한 시간 계획]
{json.dumps(time_plan, ensure_ascii=False)}

[허용 참조]
{json.dumps(allowed_refs, ensure_ascii=False)}

[등록 성경 근거]
{build_grounding(evidence, max_chars=1450)}

[등록 원어 근거]
{original_block}

[본문 해석 흐름 준비상태]
{build_interpretation_flow_prompt(evidence, originals, [])}

[영어 번역본 사용 우선순위]
{build_translation_policy_prompt(evidence, originals)}

[시대·정치 적용 안전원칙]
{build_social_context_policy_prompt(payload.get('topic', ''), payload.get('details', ''))}

다음 JSON 형식만 반환하십시오.
{{
  "title":"설교 제목",
  "core_message":"한 문장의 핵심 메시지",
  "points":[
    {{"title":"대지 제목","reference":"허용 참조 1개","explanation":"본문에 근거한 설명","application":"삶의 적용","illustration_direction":"예화 방향"}},
    {{"title":"대지 제목","reference":"허용 참조 1개","explanation":"본문에 근거한 설명","application":"삶의 적용","illustration_direction":"예화 방향"}},
    {{"title":"대지 제목","reference":"허용 참조 1개","explanation":"본문에 근거한 설명","application":"삶의 적용","illustration_direction":"예화 방향"}}
  ],
  "gospel_connection":"등록 근거 범위 안의 복음 연결 방향",
  "closing_direction":"결론과 기도의 방향"
}}"""
    return system, user
