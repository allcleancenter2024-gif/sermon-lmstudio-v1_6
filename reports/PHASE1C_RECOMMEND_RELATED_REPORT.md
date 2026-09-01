# Phase 완료 보고: recommend_related 후보 filtering 분리

## 변경 목적

`recommend_related`의 reference 제외·중복 제거·limit 적용만 순수 helper로 분리하고 DB 조회 및 semantic 검색 호출은 유지한다.

## 변경 내용

- `app.rag.hybrid.filter_related_candidates(candidates, reference, limit)` 추가
- `recommend_related`는 기준본문 조회와 query 구성·semantic 검색 후 helper에 위임
- `reference.strip()` 기준 제외, 후보 순서, 중복 reference 제거, limit 및 기존 KeyError semantics 유지

## 기존 기능 영향

- `/api/recommend`, `/api/study` 응답 형식 변경 없음
- SQLite schema/data 및 Provider 호출 변경 없음
- `fuse_hybrid_results`와 semantic scoring 동작 변경 없음

## 테스트

- 변경 전 관련 테스트: `42 passed in 9.66s`
- 변경 후 관련 테스트: `42 passed in 9.67s`
- 변경 후 전체 pytest: `212 passed in 22.37s`

## Rollback 방법

`recommend_related` 내부 filtering loop를 복원하고 `filter_related_candidates` import/함수를 제거하면 된다. DB rollback은 필요하지 않다.

## 다음 단계

Phase 1 RAG의 저위험 순수/저장 경계 분리가 완료됐다. 다음 RAG 이동은 semantic/hybrid orchestration 전체 또는 Router로 확장되므로 새 의존성 분석과 승인을 먼저 수행한다.
