# Phase 2B RRF Hybrid 완료 보고

## 작업 전 Baseline

Git metadata가 없는 작업 디렉터리이며 제품 버전 후보는 `sermon-lmstudio-final-package-v40`이다. `RAG_FUSION_STRATEGY=legacy_weighted`, `RAG_LEXICAL_STRATEGY=legacy`, FTS5 지원 상태였고 전체 기준선은 **212 passed** (`21.83s`)였다.

## 기존 Hybrid 구조

Semantic Search와 Legacy/FTS5 Lexical 후보를 `app.rag.hybrid`에서 결합하고, core public wrapper와 main 호출부는 유지한다.

## 기존 Weighted 계산식

Semantic rank 후보는 `0.75 * max(semantic_score, 0)`, lexical rank 후보는 `0.25 * (1 - rank / max(len(lexical), 1))`로 합산했다.

## 새 RRF 구조

`rrf_fusion(semantic, lexical, limit, k)`를 추가했다. 각 입력 목록의 rank만 사용하며 semantic/lexical 점수 자체를 비교하지 않는다. `hybrid_search(..., fusion="rrf")` 또는 환경설정으로 선택한다.

## RRF k 값

기본 `k=60`을 함수 기본값으로 단일 정의했다. 후보 규모(top 32)에서 안정적인 초기값이며 추후 평가로 조정 가능하다.

## Evidence Identity Key

두 결과의 공통 `id`(passage/source id)를 고유 identity로 사용한다. text 전체 비교는 하지 않는다.

## 중복 병합 방식

양쪽에 모두 있으면 `1/(k+semantic_rank) + 1/(k+lexical_rank)`를 합산하고, 한쪽에만 있으면 해당 항만 사용한다. 동점은 `id ASC`로 정렬해 deterministic ranking을 보장한다.

## 변경 파일

- `app/rag/hybrid.py`
- `app/core.py`
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE2B_RRF_HYBRID_REPORT.md`

## Feature Flag

`RAG_FUSION_STRATEGY=legacy_weighted|rrf`를 지원하며 기본값은 `legacy_weighted`다. Lexical 선택(`RAG_LEXICAL_STRATEGY=legacy|fts5`)과 fusion 선택은 독립적이다.

## Fallback 구조

알 수 없는 fusion 값은 `legacy_weighted`로 안전하게 fallback한다. RRF 함수 자체는 이미 검색된 목록만 처리하며 DB 재검색·embedding·LM 호출을 하지 않는다.

## Lexical 전략과의 조합

Legacy+Weighted(기본), FTS5+Weighted, Legacy+RRF, FTS5+RRF 네 조합을 동일한 `hybrid_search` API로 구성할 수 있다.

## Result Schema 영향

기존 필드는 유지한다. RRF 결과에는 `semantic_rank`, `lexical_rank`, `rrf_score`, `fusion_strategy="rrf"`를 추가하며 `id`, reference, text 등 기존 metadata는 보존한다.

## DB 영향

RRF는 in-memory fusion만 수행하며 schema/data 변경이 없다.

## Evidence Packet 영향

후속 Evidence Packet에 전달되는 후보의 필드와 source metadata는 유지된다. 최종 limit도 기존 인자를 그대로 사용한다.

## Preflight 영향

Preflight 규칙과 본문/evidence 판정은 변경하지 않았다.

## Grounding 영향

Grounding 정책·validator·citation 규칙은 변경하지 않았다.

## LM Studio 영향

RRF는 Provider를 호출하지 않는다. embedding/generation 호출 횟수 증가가 없다.

## A/B Query Set

임시 DB 복사본에서 reference 3개(`요한복음 3:16`, `로마서 8:28`, `미가 6:8`), 한국어 8개(`두려움`, `은혜`, `용서`, `사랑`, `구원`, `칭의`, `성화`, `하나님의 주권`), 영문 3개(`grace`, `faith`, `salvation`), 복합 질의 1개를 비교했다. 한국어 일반어는 현재 DB의 자료 특성상 결과가 없었다.

## Legacy Weighted 결과

기존 weighted fusion 및 API wrapper 테스트가 통과했으며 기본 전략은 계속 이 경로를 사용한다.

## RRF 결과

합성 unit 입력에서 양쪽 중복 evidence의 score 합산, 단일 목록 evidence 보존, deterministic id tie-break를 확인했다.

## FTS5 + Weighted 결과

FTS5 lexical 후보를 weighted fusion에 연결할 수 있으며 기존 FTS5 전략과 weighted 계산식은 그대로 유지된다.

## FTS5 + RRF 결과

FTS5 lexical 후보를 RRF fusion에 연결할 수 있다. 실제 임시 DB에서 FTS index 31,098건 구축과 15개 query 실행을 확인했다.

## 검색 품질 비교

15개 query의 결과 count를 비교한 결과 reference/영문 질의는 Legacy와 FTS5가 각각 top 8을 반환했고 한국어 질의는 양쪽 모두 0건이었다. 정답 label이 없어 Precision/Recall/MRR를 산출하지 않았으며 RRF 우수성을 확정하지 않았다.

## 성능 비교

동일 임시 DB 15개 query, 순차 실행 총시간 기준 Legacy lexical **387.59ms**, FTS5 **451.18ms**였다. 이는 단일 benchmark이며 FTS5 index/환경 영향을 포함한다. RRF 계산 자체는 검색 목록 in-memory 처리다.

## 안정성 비교

RRF unit 결과와 기존 회귀 테스트가 통과했다. top_k, identity 병합, deterministic 정렬을 보장한다.

## 관련 테스트 결과

RRF/기존 RAG·Generation·Evidence·Preflight·Backup 회귀: **59 passed in 13.29s**.

## 전체 pytest 결과

**212 passed in 22.25s**, failed 0, error 0.

## 발견된 문제

없음. 다만 Git status/branch는 repository metadata 부재로 확인할 수 없다.

## 남은 위험

현재 한국어 자료 분포와 tokenizer 특성상 FTS5 품질이 질의별로 달라질 수 있다. RRF 정량 우열은 relevance label이 있는 평가 세트가 필요하다. FTS5 index 자동 동기화는 이전 Phase의 관리용 rebuild 정책을 따른다.

## 권장 기본 전략

이번 단계에서는 **Legacy Weighted 유지**를 권장한다. RRF는 선택 가능한 A/B 경로로만 제공하며 기본값을 변경하지 않는다.

## Rollback 방법

`RAG_FUSION_STRATEGY=legacy_weighted`로 설정하고 `fusion="rrf"` 호출을 제거하면 즉시 기존 weighted 경로로 복귀한다. 필요 시 `rrf_fusion` import와 구현을 제거해도 DB rollback은 필요 없다.

## 다음 권장 단계

이번 Phase 2B 범위에서 중단한다. RRF 기본값 전환, Legacy 삭제, Grounding Validator/Audit, Router/UI 변경은 별도 승인 후 진행한다.
