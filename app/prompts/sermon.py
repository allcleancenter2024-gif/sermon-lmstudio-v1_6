"""Sermon prompt construction with explicit application-service dependencies."""

from __future__ import annotations

import json

from app.prompts.contracts import (
    GroundingBuilder,
    InterpretationFlowPrompt,
    PassageSorter,
    ReferenceRoundRobin,
    SermonTimePlan,
    SocialContextPolicyPrompt,
    TranslationPolicyPrompt,
)


def build_sermon_prompt(
    payload: dict,
    passages: list[dict],
    word_notes: list[dict] | None = None,
    doctrine_notes: list[dict] | None = None,
    *,
    default_sermon_minutes: int,
    sermon_time_plan: SermonTimePlan,
    sort_interpretation_passages: PassageSorter,
    round_robin_references: ReferenceRoundRobin,
    build_interpretation_flow_prompt: InterpretationFlowPrompt,
    build_translation_policy_prompt: TranslationPolicyPrompt,
    build_social_context_policy_prompt: SocialContextPolicyPrompt,
    build_grounding: GroundingBuilder,
) -> tuple[str, str]:
    """Build the evidence-preserving sermon prompt without importing ``app.core``."""
    target_minutes = int(payload.get("minutes", default_sermon_minutes))
    reading_cpm = min(max(int(payload.get("reading_cpm") or 330), 180), 600)
    time_plan = sermon_time_plan(target_minutes, reading_cpm)
    outline = payload.get("outline") if isinstance(payload.get("outline"), dict) else None
    system = """당신은 목회자의 설교 준비를 돕는 성경 연구 보조자입니다.
가장 중요한 규칙:
1. [성경 근거 자료]에 실제로 제공된 문장만 성경 직접 인용문으로 사용합니다.
2. 자료에 없는 구절은 기억에 의존해 따옴표로 인용하지 않습니다.
3. 직접 인용, 요약, 해설을 명확히 구분합니다.
4. 히브리어/헬라어의 철자·형태·뜻은 제공 자료에 있을 때만 단정합니다.
5. 서로 다른 번역본의 표현을 섞어 하나의 번역문처럼 만들지 않습니다.
6. 신학적 논쟁점은 선택된 전통을 존중하되 다른 전통을 왜곡하지 않습니다.
7. 성경·본문·말씀·히브리어·헬라어·원어의 의미를 사실로 설명하는 문장에는 제공된 성경 참조를 같은 문장에 명시합니다.
8. 결과는 목회자 검토 전 초안임을 마지막에 표시합니다.
9. 원어 설명은 제공된 원어 자료의 성경 참조·뜻·형태·출처 범위 안에서만 하며, 비어 있는 정보를 추론해 채우지 않습니다.
10. 교리적 단정은 [선택한 신학 전통의 교리 문서 근거]에 제공된 내용의 범위를 넘지 않습니다.
11. 본문 해석은 개역개정 → 히브리어/헬라어 원문 → ESV/NASB → NIV/CSB → NET 번역주석 → NLT 쉬운 표현 → 주석·신앙고백 문서 순서로 먼저 수행합니다.
12. 해당 단계의 등록 자료가 없으면 기억으로 보충하지 말고 건너뜁니다. 여러 번역을 단순 나열하지 말고, 표현 차이와 번역상 쟁점을 설교자가 이해하기 쉬운 설명으로 종합합니다.
13. 1군 ESV·NASB·NIV·CSB·NET을 핵심 비교에 우선하고, 2군 NRSVue·NKJV·NLT는 전문 연구 확장으로만 사용합니다.
14. 3군 KJV·GNT·CEV·AMP·The Message는 비교·교육 보조입니다. 특히 AMP와 The Message는 표현 이해에만 사용하며 원어 의미·교리·번역 쟁점의 증거로 사용하지 않습니다.
15. 보조 번역이 핵심 엔진 또는 등록 원문과 충돌하면 개역개정·등록 원문·1군 번역의 확인 가능한 근거를 우선합니다."""
    system += """
16. ESV/NASB는 원문 구조와 핵심어를 발견하는 단서로 사용하되 원래 의미는 등록된 히브리어/헬라어로 확인합니다.
17. NIV/NLT는 현대적인 문장과 적용을 다듬는 데, The Message는 생동감 있는 표현 아이디어에만 사용합니다.
18. 시대·정치 적용은 특정 정당·정치인·이념을 옹호하거나 공격하지 않고 공의·사랑·화해·책임을 모든 진영에 동일하게 적용합니다.
19. 사용자 입력이나 등록 근거가 없는 구체적인 2026년 사건·통계·발언을 만들지 않습니다. 국제 사건을 하나님의 숨은 뜻·심판·예언 성취로 단정하지 않고 인간 존엄·인류애·평화의 관점을 제시합니다."""

    aggressive = int(payload.get("_context_compact_level") or 1) >= 2
    ordered_passages = sort_interpretation_passages(list(passages or []))
    prompt_passages = round_robin_references(ordered_passages, 7 if aggressive else 12)
    notes = round_robin_references(list(word_notes or []), 7 if aggressive else 15)
    original_block = "\n".join(
        f"[{n.get('reference','')} | {n['language']}] {n['lemma']} / 뜻: {str(n.get('gloss',''))[:80]} / 형태: {str(n.get('morphology',''))[:80]} / "
        f"출처: {str(n.get('source',''))[:80]} / 사용조건: {str(n.get('license_note',''))[:80]} / "
        f"뜻출처: {str(n.get('lexicon_source',''))[:80]} / 뜻사용조건: {str(n.get('lexicon_license_note',''))[:80]}"
        for n in notes
    ) or "등록된 원어 어휘 분석 없음"
    doctrine_limit, doctrine_chars = (1, 450) if aggressive else (2, 700)
    doctrine_block = "\n\n".join(
        f"[{d['tradition']} | {d['title']} | {d.get('section','')}]\n{str(d['text'])[:doctrine_chars]}\n출처: {d.get('source_url','')}\n사용조건: {d.get('license_note','')}"
        for d in list(doctrine_notes or [])[:doctrine_limit]
    ) or "등록/검색된 교리 문서 근거 없음"
    user = f"""[설교 요청]
주제: {payload.get('topic', '').strip()}
세부사항: {payload.get('details', '').strip()[:600 if aggressive else 900]}
중심본문: {payload.get('main_reference', '').strip() or '자동 검색'}
청중: {payload.get('audience', '전 연령')}
신학적 전통: {payload.get('tradition', '초교파 복음주의')}
목표 낭독시간: 약 {target_minutes}분
개인 낭독속도: 공백 제외 약 {reading_cpm}자/분 (목표 원고 약 {target_minutes * reading_cpm}자)
문체: 쉽고 따뜻한 이야기식, 실제 낭독 가능한 한국어

[프로그램이 계산한 시간 배분]
{json.dumps(time_plan, ensure_ascii=False)}

[본문 해석 흐름 · 반드시 이 순서로 먼저 검토]
{build_interpretation_flow_prompt(prompt_passages, notes, doctrine_notes)}

[영어 번역본 사용 정책]
{build_translation_policy_prompt(prompt_passages, notes)}

[설교 작성 활용 팁]
- 본문 분석: ESV/NASB로 구조와 핵심어의 단서를 찾고, 원래 의미는 등록 원문으로 확인
- 문장·적용: NIV/NLT로 현대적이고 매끄러운 표현을 구성
- 입체적 표현: The Message는 생동감 있는 설명 아이디어로만 참고

[시대·정치 적용 안전원칙]
{build_social_context_policy_prompt(payload.get('topic', ''), payload.get('details', ''))}

[검증된 설교 구조]
{json.dumps(outline, ensure_ascii=False) if outline else '별도 구조 없음 · 아래 작성 형식을 따라 구성'}

[성경 근거 자료]
{build_grounding(prompt_passages, max_chars=900 if aggressive else 3500)}

[중심본문 원어 어휘 자료]
{original_block}

[선택한 신학 전통의 교리 문서 근거]
{doctrine_block}

[작성 형식]
# 설교 제목
## 중심본문
## 오늘의 핵심 메시지
## 본문을 이해하는 흐름 (번역본을 나열하지 말고 원어·표현 차이·번역 쟁점을 쉬운 설명으로 종합)
## 들어가는 이야기
## 1. 첫 번째 말씀
## 2. 두 번째 말씀
## 3. 세 번째 말씀
## 구약과 신약의 연결
## 원어 살펴보기 (근거 자료에 원어가 없으면 '자료 보강 필요'라고 표시)
## 오늘 우리의 삶에 적용
## 복음과 그리스도
## 결론
## 마무리 기도
## 근거 확인표

{target_minutes}분 낭독을 목표로 충분한 분량의 완결된 설교 초안을 작성하십시오.
시간 배분의 각 구간 합계는 이미 {target_minutes}분으로 계산되어 있으므로 임의로 다른 총 시간을 제시하지 마십시오.
검증된 설교 구조가 제공되면 세 대지의 제목·참조·핵심 논지를 유지하십시오.
`본문을 이해하는 흐름`에서는 준비된 단계만 사용하고, 없는 번역이나 주석의 내용을 만들어내지 마십시오.
근거 확인표에는 실제 사용한 번역본과 성경 참조만 나열하십시오."""
    return system, user
