# Phase 완료 보고

## 변경 목적

Bible·Doctrine embedding의 read-only 통계 조회만 별도 RAG Repository로 분리했다. vector 생성·검색·Provider 호출은 이동하지 않았다.

## 변경 파일

- `app/repositories/rag.py` — 신규 `fetch_rag_stats`와 기존 embedding table bootstrap
- `app/core.py` — `rag_stats`를 repository에서 re-export하는 facade
- `reports/CORE_DEPENDENCY_MAP.md` — RAG 분리 현황 갱신

## 변경 내용

- Repository가 Bible `rag_embeddings`와 Doctrine `doctrine_embeddings`의 count 및 model 목록을 기존 SQL로 조회한다.
- 기존 반환 키·값 타입·model 정렬을 유지했다.
- `build_rag_index`, `semantic_search`, `hybrid_search`, `recommend_related`, Doctrine vector 함수는 이동하지 않았다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리와 `app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- health/status/database dashboard에서 사용하는 `app.core.rag_stats` 경로 유지.
- 삭제 함수는 불허 상태로 실행하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v20_database.py`, `tests/test_e2e_v6.py` — `42 passed in 9.75s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `42 passed in 9.66s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 22.47s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- RAG table bootstrap이 `app.core.init_db`와 `app.repositories.rag`에 중복되어 있다. 기존 public 함수의 독립 호출 호환성을 위한 제한된 중복이다.
- vector 생성·검색은 Provider와 binary vector schema에 결합되어 core에 남아 있다.

## Rollback 방법

1. `app/core.py`에 기존 `rag_stats` 직접 조회 구현을 복원하고 `fetch_rag_stats` import를 제거한다.
2. `app/repositories/rag.py`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 RAG 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

삭제 함수는 사용자 불허로 보류한다. 다음은 RAG `semantic_search` 또는 `build_rag_index`의 raw/Provider 경계를 다시 분석하고 별도 승인한다. Phase 2 Router 분리는 시작하지 않는다.
