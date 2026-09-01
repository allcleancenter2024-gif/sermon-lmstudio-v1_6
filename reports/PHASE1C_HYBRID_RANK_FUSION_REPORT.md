# Phase 완료 보고: hybrid rank fusion 분리

## 변경 목적

`hybrid_search`의 순수 lexical·semantic 결과 융합만 별도 모듈로 분리하고 검색 호출과 API 계약은 유지한다.

## 변경 내용

- `app.rag.hybrid.fuse_hybrid_results(semantic, lexical, limit)` 추가
- 기존 `0.75/0.25` 가중치, 중복 id 합산, lexical-only row 처리, 정렬, `rag_score` 반올림을 그대로 이동
- `app.core.hybrid_search`는 `search_passages`와 `semantic_search` 호출 후 helper에 위임

## 기존 기능 영향

- API URL/응답 형식, Provider 호출, SQLite schema/data 변경 없음
- lexical 및 semantic 검색 결과의 기존 우선순위와 병합 규칙 유지
- `recommend_related` 및 Router 분리는 시작하지 않음

## 테스트

- 변경 전 관련 테스트: `42 passed in 9.67s`
- 변경 후 관련 테스트: `42 passed in 9.71s`
- 변경 후 전체 pytest: `212 passed in 22.61s`

## Rollback 방법

`core.py`에 기존 fusion loop를 복원하고 `fuse_hybrid_results` import 및 `app/rag/hybrid.py`를 제거하면 된다. DB rollback은 필요하지 않다.

## 다음 단계

남은 RAG 후보는 `recommend_related`의 reference 제외 orchestration이다. semantic 결과와 공개 추천 응답에 결합되므로 먼저 분석하고 별도 승인 후 진행한다.
