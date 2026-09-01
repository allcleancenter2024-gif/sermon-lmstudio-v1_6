# Phase 완료 보고

## 변경 목적

Doctrine 검색에서 raw vector/source 조회만 Repository로 분리하고, Provider query embedding·binary 복원·cosine scoring은 Core에 유지했다.

## 변경 파일

- `app/repositories/doctrine.py` — `fetch_doctrine_vector_rows` 추가
- `app/core.py` — `doctrine_search`가 raw vector helper를 사용하도록 변경
- `reports/CORE_DEPENDENCY_MAP.md` — Doctrine 검색 경계 갱신

## 변경 내용

- Repository가 기존 JOIN, model 필터, tradition/공통 필터와 결과 필드를 동일하게 조회한다.
- Core가 LMStudio query embedding, qnorm 계산, `vector_blob` 복원, dot/cosine score, 정렬·limit를 계속 수행한다.
- `doctrine_search` public 함수명·서명·결과 필드·점수 semantics를 유지했다.
- Schema·데이터·Provider 호출 계약을 변경하지 않았다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- Doctrine 및 sermon generation의 tradition 필터·점수 정렬 유지.
- 순환 import 없음.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py` — `35 passed in 9.05s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `35 passed in 8.83s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 39.28s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- vector dimension mismatch와 scoring 규칙은 Core에 남아 있으며, Provider 응답 형식 변경 시 함께 검토해야 한다.
- `doctrine_search`는 여전히 Provider query embedding과 vector scoring을 조합한다.

## Rollback 방법

1. `app/core.py`에 기존 `doctrine_search` 직접 JOIN 조회를 복원하고 `fetch_doctrine_vector_rows` import를 제거한다.
2. `app/repositories/doctrine.py`의 helper를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 DOCTRINE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

Doctrine vector read 경계까지 분리했으므로, 남은 scoring·Provider 책임은 즉시 이동하지 않는다. 다음 단계는 `bible_database_dashboard` 또는 삭제 함수의 read/write boundary를 다시 분석하고 별도 승인한다. Phase 2 Router 분리는 시작하지 않는다.
