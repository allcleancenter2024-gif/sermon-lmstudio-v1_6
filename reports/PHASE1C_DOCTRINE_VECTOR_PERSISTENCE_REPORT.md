# Phase 완료 보고

## 변경 목적

Doctrine index 생성에서 Provider embedding과 vector 계산은 Core에 유지하고, precomputed vector batch의 SQLite upsert만 Repository로 분리했다.

## 변경 파일

- `app/repositories/doctrine.py` — `persist_doctrine_embeddings` 및 embedding table bootstrap 추가
- `app/core.py` — `build_doctrine_index`가 batch upsert helper를 사용하도록 변경
- `reports/CORE_DEPENDENCY_MAP.md` — Doctrine vector 경계 갱신

## 변경 내용

- Core가 각 batch의 vector를 float binary로 packing하고 dimension·norm을 계산한다.
- Repository는 `(chunk_id, packed, dimension, norm)` 행을 받아 기존 upsert SQL로 저장하고 batch 단위 transaction을 commit한다.
- Provider 호출 실패는 DB upsert 전에 발생하며, upsert 오류는 해당 batch transaction을 rollback하는 기존 semantics를 유지한다.
- `build_doctrine_index` public 함수명·서명·반환 count·batch 반복을 유지했다.
- `doctrine_search`의 query embedding·binary 복원·cosine 계산은 이동하지 않았다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- vector_blob·dimension·norm 저장 형식과 conflict update 규칙 유지.
- 순환 import 없음.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py` — `35 passed in 8.54s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `35 passed in 8.78s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 23.34s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- embedding dimension 불일치 검증은 기존처럼 Core/Provider 결과에 의존하며 새 검증을 추가하지 않았다.
- `doctrine_search`와 RAG vector read path는 여전히 Core에 남아 있다.

## Rollback 방법

1. `app/core.py`에서 기존 batch별 직접 upsert loop를 복원하고 `persist_doctrine_embeddings` import를 제거한다.
2. `app/repositories/doctrine.py`의 persistence helper와 bootstrap을 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 DOCTRINE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 Doctrine 후보인 `doctrine_search`는 Provider·vector 계산·tradition filter가 결합되어 있으므로 즉시 이동하지 않는다. 필요 시 raw vector 조회와 scoring을 별도 분석·승인한다. Phase 2 Router 분리는 시작하지 않는다.
