# Phase 완료 보고: semantic_search scoring 분리

## 변경 목적

`semantic_search`의 순수 벡터 점수 계산만 helper로 분리하고 Provider 호출, vector 복원, 결과 shaping은 유지한다.

## 변경 내용

- `app.rag.semantic.score_semantic_vector(query_vector, vector, stored_norm)` 추가
- stored norm 경로와 `cosine_similarity` fallback을 기존 식 그대로 이동
- `app.core.semantic_search`는 helper 호출만 수행

## 호환성

- dimension mismatch·빈 벡터·zero norm sentinel `-1.0` 유지
- API URL/응답 형식, SQLite schema/data, Provider 호출, hybrid rank fusion 변경 없음
- `core._cosine` compatibility alias 유지

## 테스트

- 변경 전 관련 테스트: `42 passed in 9.71s`
- 변경 후 관련 테스트: `42 passed in 9.80s`
- 변경 후 전체 pytest: `212 passed in 22.59s`

## Rollback

`semantic_search`에 기존 if/else scoring 블록을 복원하고 `score_semantic_vector` import/함수를 제거하면 된다. DB rollback은 필요하지 않다.

## 다음 단계

`hybrid_search` rank fusion은 lexical·semantic 결과와 가중치 정책을 결합하므로 별도 분석과 승인을 받은 뒤 진행한다. Router 분리는 시작하지 않는다.
