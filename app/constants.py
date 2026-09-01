"""Stable, dependency-free application constants.

This module deliberately imports only the standard library so it can be used by
configuration and provider modules without creating a dependency on app.core.
"""

import re


SUPPORTED_SERMON_MINUTES = (15, 20, 25, 30, 40)
DEFAULT_SERMON_MINUTES = 15
DEFAULT_LMSTUDIO_URL = "http://127.0.0.1:12345/v1"
LEGACY_LMSTUDIO_URL = "http://127.0.0.1:1234/v1"

INTERPRETATION_FLOW_DEFINITION = (
    ("korean_base", "1. 개역개정 본문", "개역개정 본문을 해석의 출발점으로 읽습니다."),
    ("original_language", "2. 히브리어·헬라어 원문", "본문에 실제 연결된 lemma·형태·뜻만 확인합니다."),
    ("formal_equivalence", "3. ESV/NASB 직역 비교", "문장 구조와 핵심 표현의 차이를 확인합니다."),
    ("meaning_equivalence", "4. NIV/CSB 의미 비교", "문맥상 의미를 어떻게 풀어 전달하는지 확인합니다."),
    ("translation_notes", "5. NET 번역·번역주석", "NET 본문은 번역 비교에, 별도 NET Notes는 번역상 쟁점 확인에 사용합니다."),
    ("easy_expression", "6. NLT 쉬운 표현", "어려운 내용을 회중이 이해하기 쉬운 말로 바꾸는 데 참고합니다."),
    ("doctrine", "7. 주석·신앙고백 문서", "선택한 신학 전통과 일치하는 등록 문서로 해석을 점검합니다."),
    ("sermon", "8. 설교 작성", "앞 단계의 차이와 쟁점을 나열하지 않고 한 흐름으로 종합합니다."),
)

ENGLISH_TRANSLATION_POLICY = (
    ("tier1", "1군 · 핵심 엔진", ("ESV", "NASB", "NIV", "CSB", "NET"), "본문 해석과 번역 비교에 우선 사용"),
    ("tier2", "2군 · 전문 연구 확장", ("NRSVUE", "NKJV", "NLT"), "핵심 엔진의 연구를 보완"),
    ("tier3", "3군 · 비교·교육 보조", ("KJV", "GNT", "CEV", "AMP", "THE MESSAGE"), "비교·교육·표현 이해에만 보조 사용"),
)

SOCIAL_CONTEXT_CUE_RE = re.compile(
    r"(정치|정당|정치인|대통령|국회|정부|선거|이념|보수|진보|사회적?\s*갈등|양극화|"
    r"경제|물가|유가|빈곤|불평등|전쟁|국제|세계정세|외교|평화|난민|인권)", re.IGNORECASE
)

REFERENCE_RE = re.compile(r"([가-힣A-Za-z]+\s*\d{1,3}:\d{1,3}(?:-\d{1,3})?)")
EVIDENCE_CUE_RE = re.compile(r"(성경은|성경에|본문은|본문이|말씀은|말씀에|기록되어|기록된|히브리어|헬라어|원어)")
ORIGINAL_CUE_RE = re.compile(r"(히브리어|헬라어|원어)")
DOCTRINE_CUE_RE = re.compile(r"(교리|신앙고백|웨스트민스터|하이델베르크)")
DIRECT_QUOTE_RE = re.compile(r'[“\"]([^”\"]{4,})[”\"]|‘([^’]{4,})’')
POLITICAL_ENTITY_RE = re.compile(r"(특정\s*)?(정당|정치인|후보|대통령|국회의원|정부|여당|야당|보수|진보|좌파|우파|선거|투표)")
PARTISAN_DIRECTIVE_RE = re.compile(r"(지지해야|반대해야|비판해야|찍어야|뽑아야|투표해야|표를\s*줘야|몰아내야|퇴출해야|심판해야|악의\s*편|옳은\s*편)")
WORLD_AFFAIRS_RE = re.compile(r"(전쟁|국가|민족|정부|진영|국제\s*질서|세계정세)")
DIVINE_CERTAINTY_RE = re.compile(r"(하나님의\s*(?:숨은\s*)?뜻|하나님의\s*심판|예언의\s*성취|하나님(?:께서|이)\s*.{0,20}(?:벌하|택하|지지하|승리하게))")
NEUTRALITY_DISCLAIMER_RE = re.compile(r"(아니|않|말아야|해서는\s*안|금지|지양|피해야|경계해야|단정할\s*수\s*없)")

REVIEW_STATUSES = {"comment", "changes_requested", "approved"}
