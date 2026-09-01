# Phase 1 RAG orchestration 전체 분리 분석

## 현재 상태

저위험 단위인 raw 조회, vector packing, SQLite upsert, cosine 계산, vector 복원, scoring, hybrid fusion, recommendation filtering이 각각 분리되었다. `app.core`에는 public compatibility 함수와 외부 경계 orchestration이 남아 있다.

## 남은 orchestration

| 함수 | 남은 책임 | 결합도 | 권장 판단 |
|---|---|---:|---|
|`build_rag_index`|Provider 호출, batch 입력, helper 조합|중간|현 상태 유지 가능; 이동 시 Provider protocol 필요|
|`semantic_search`|DB bootstrap, Provider query embedding, row 조회/복원, score, shaping|중간~높음|한 번에 이동하지 말고 adapter 설계 선행|
|`hybrid_search`|lexical/semantic 호출과 pure fusion 조합|중간|검색 함수 주입 경계가 필요|
|`recommend_related`|DB 기준본문, query 구성, semantic 호출, pure filtering|중간|Bible `compare_reference` 의존으로 독립 이동 어려움|

## 안전한 이동 방향

`app.rag.semantic`이 Repository나 Provider concrete class를 import하면 cycle 및 테스트 patch 경로가 깨질 수 있다. 전체 orchestration을 옮길 경우 concrete import 대신 다음 중 하나가 필요하다.

1. 함수 인자 주입: `embedding_fn`, `fetch_rows`, `init_fn`
2. Protocol 정의: embedding client와 row reader 계약을 RAG 모듈에 선언
3. `core.py` compatibility facade에서 기존 public 함수와 patch point를 유지

현재 구조에서는 (1) 또는 (2)를 도입하는 순간 함수 signature/테스트 mocking surface가 넓어져 저위험 단위가 아니다.

## 권장 다음 단계

새 코드 이동보다 먼저 `semantic_search` orchestration의 호출 계약을 문서화하고, Provider·Repository를 concrete import하지 않는 adapter 설계를 승인받는 것이 안전하다. Router 분리는 Phase 2이므로 시작하지 않는다.

## 승인 요청

다음 실제 리팩터링 전에 `semantic_search` orchestration adapter 설계(코드 변경 없음)를 먼저 검토할지, 또는 현재 Phase 1 RAG 분리를 완료 상태로 동결할지 결정이 필요하다.
