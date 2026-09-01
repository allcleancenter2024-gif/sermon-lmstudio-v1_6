# Phase 완료 보고

## 변경 목적

Doctrine vector indexing 흐름에서 raw chunk 조회만 Repository로 분리했다. LMStudio embedding, vector packing, norm 계산, embedding upsert와 검색은 Core에 유지했다.

## 변경 파일

- `app/repositories/doctrine.py` — `fetch_doctrine_chunks` 추가
- `app/core.py` — `build_doctrine_index`가 raw chunk helper를 사용하도록 변경
- `reports/CORE_DEPENDENCY_MAP.md` — Doctrine 분리 현황 갱신

## 변경 내용

- Repository가 기존 SQL `SELECT id, tradition, title, section, text FROM doctrine_chunks ORDER BY id`를 수행한다.
- Core는 기존대로 LMStudio `embeddings`, batch 처리, float binary packing, norm/dimension 계산과 `doctrine_embeddings` upsert를 수행한다.
- `build_doctrine_index` public 함수명·서명·반환 count·batch semantics를 유지했다.
- `doctrine_search`와 Provider/vector 책임은 이동하지 않았다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리·`app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- Doctrine index/search 결과 및 embedding 호출 순서 유지.
- 순환 import 없음.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py` — `35 passed in 14.13s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `35 passed in 8.53s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 21.98s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `build_doctrine_index`는 외부 Provider 호출과 vector DB 쓰기를 결합하고 있어 전체 이동하지 않았다.
- `doctrine_search`는 query embedding·binary vector 계산·tradition policy를 결합하고 있어 별도 경계 분석이 필요하다.

## Rollback 방법

1. `app/core.py`에서 기존 doctrine chunk 직접 조회를 복원하고 `fetch_doctrine_chunks` import를 제거한다.
2. `app/repositories/doctrine.py`의 helper를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 DOCTRINE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 Doctrine 후보는 vector persistence의 raw upsert와 Provider embedding을 분리하는 경계다. 이는 transaction·vector dimension·embedding 실패 처리에 영향을 줄 수 있으므로 별도 분석과 승인을 먼저 받는다. Phase 2 Router 분리는 시작하지 않는다.
