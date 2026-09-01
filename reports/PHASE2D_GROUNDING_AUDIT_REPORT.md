# Phase 2D Grounding Audit 완료 보고

## 작업 전 Baseline

Git metadata가 없는 작업 디렉터리이며 제품 버전 후보는 `sermon-lmstudio-final-package-v40`이다. Grounding Validator와 Audit은 기본 비활성, 전체 pytest 기준선은 **212 passed** (`22.02s`)였다.

## 기존 Citation Validation 구조

기존 `analyze_citations()`와 `validate_quotes()`는 생성 후 명시 reference/직접 인용의 기계적 검사를 수행한다. 이 기능은 삭제·교체하지 않았다.

## Grounding Audit 위치

`app.grounding.audit`에 생성 후 독립 실행되는 claim 추출·Evidence matching·report 모델을 추가했다. Sermon Service는 `GROUNDING_AUDIT_ENABLED=true`일 때만 결과를 optional response metadata로 부착한다.

## Claim Types

`scripture_quote`, `scripture_claim`, `original_language_claim`, `doctrine_claim`, `statistical_claim`, `historical_claim`, `external_fact`, `application_statement`, `general_statement`를 지원한다.

## Claim Extraction 규칙

기존 `REFERENCE_RE`, `DIRECT_QUOTE_RE`, `EVIDENCE_CUE_RE`, `ORIGINAL_CUE_RE`, `DOCTRINE_CUE_RE`와 간단한 숫자/역사/외부사실/권면 regex를 사용한다. 한국어 문장 종결부호와 줄바꿈을 기준으로 보수적으로 분리한다.

## Evidence Matching 규칙

동일 reference를 우선 매칭하고, 직접 인용은 공백·문장부호를 제거한 제한적 substring 비교를 사용한다. Audit 중 RAG 재검색, 전체 text fuzzy matching, embedding 생성은 하지 않는다.

## Grounded 판정 규칙

명시 reference와 Evidence가 연결되면 scripture claim은 grounded다. 직접 인용은 해당 reference의 등록 본문과 일치할 때 grounded다. 원어/교리 claim도 해당 Evidence가 연결될 때 grounded다.

## Partially Grounded 판정 규칙

직접 인용의 reference는 확인되지만 인용 일부가 등록 본문과 불일치하면 partially_grounded로 표시한다.

## Ungrounded 판정 규칙

명시 reference 또는 해당 Evidence가 없는 scripture/original/doctrine claim, 출처 없는 통계·역사·외부 사실은 ungrounded다. 생성 실패나 자동 차단으로 전파하지 않는다.

## Not Applicable 판정 규칙

권면·적용 문장과 일반적인 수사 문장은 not_applicable로 분류하며 grounding coverage 분모에서 제외한다.

## 변경 파일

- `app/grounding/audit.py`
- `app/services/sermon_service.py`
- `reports/PHASE2D_GROUNDING_AUDIT_REPORT.md`

## Feature Flag

`GROUNDING_AUDIT_ENABLED=false` 기본값이다. true일 때도 본문은 수정하지 않고 audit metadata만 추가한다.

## Generation Pipeline 영향

기존 생성·resize·Prompt·Provider 순서는 그대로다. Audit은 생성 완료 후 독립적으로 실행된다.

## Grounding Validator 영향

생성 전 Validator와 생성 후 Audit을 별도 모듈로 유지한다. Tier 정책과 Validator 판정은 변경하지 않았다.

## Evidence Packet 영향

생성 시 사용한 passages/original/doctrine 목록을 재사용하며 Audit 때문에 RAG를 재실행하지 않는다.

## Citation Validator 영향

기존 Citation Validator를 보존하고 Audit과 병행한다. 직접 인용 검사는 기존 규칙과 Audit 규칙이 각각 수행된다.

## Quality Validator 영향

기존 `build_post_generation_quality()` 판정 기준과 결과를 변경하지 않았다.

## Generation Audit 영향

기존 generation audit schema/SQL은 변경하지 않았다. Audit 결과는 현재 Service optional response metadata로만 제공된다.

## RAG 영향

Semantic, Legacy/FTS5 Lexical, RRF, top_k, ranking 변경 없음.

## LM Studio 영향

추가 LM Studio 호출은 없다. Audit은 Python regex와 전달된 Evidence만 사용한다.

## 추가 LM Studio 호출 수

**0회**.

## 성능 측정

Audit은 문장 분리와 후보 목록 reference 비교만 수행하며 DB 전체 scan/RAG 재검색/embedding을 하지 않는다. 별도 latency benchmark는 수행하지 않았고 기존 생성 경로 성능에는 영향이 없다.

## 관련 테스트 결과

Grounding Audit 단위 검증과 기존 RAG·Generation·Evidence·Preflight·Backup 회귀: **59 passed in 13.23s**.

## 전체 pytest 결과

**212 passed in 22.03s**, failed 0, error 0.

## 발견된 문제

없음. Git status/branch는 repository metadata 부재로 확인할 수 없다.

## 오탐/미탐 가능성

한국어 형태소·의미 요약은 regex로 완전하게 판정할 수 없고, reference 없는 성경 요약은 보수적으로 ungrounded가 될 수 있다. 직접 인용 partial 판정은 제한적 문자열 비교다.

## 남은 위험

Audit 결과는 기본 비활성이고 현재 Generation Audit DB에 영구 저장되지 않는다. Notebook/Web/Doctrine의 풍부한 source identity adapter와 문장별 정밀 matching은 후속 개선 대상이다.

## Rollback 방법

`GROUNDING_AUDIT_ENABLED=false`를 유지하면 기존 응답/생성 결과로 즉시 복귀한다. Service의 optional audit 연결과 `app/grounding/audit.py`를 제거해도 DB rollback은 필요 없다.

## 다음 권장 단계

이번 Phase 2D 범위에서 중단한다. Audit 기본 활성화, 자동 수정/재생성, Web Grounding, UI/Router 변경은 별도 승인 후 진행한다.
