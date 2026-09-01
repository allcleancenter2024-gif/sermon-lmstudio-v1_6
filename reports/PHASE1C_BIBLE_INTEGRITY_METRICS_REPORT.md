# Phase 완료 보고

## 변경 목적

`bible_database_integrity`의 raw SQLite 검사만 Repository로 분리하고, Core의 issue 문구·정책 판정·최종 응답 조립은 유지했다.

## 변경 파일

- `app/repositories/bible.py` — `fetch_bible_integrity_metrics` 추가
- `app/core.py` — `bible_database_integrity`가 raw metrics helper를 사용하도록 변경
- `reports/CORE_DEPENDENCY_MAP.md` — DATABASE 무결성 경계 갱신

## 변경 내용

- Repository가 기존 SQL로 `quick_check`, blank passages, orphan RAG vectors, blocked fulltext를 조회한다.
- Core가 기존 한국어 issue 메시지, `ok` 판정, 반환 dict를 그대로 조립한다.
- `bible_database_dashboard`, 삭제 함수, RAG·license 정책, API 라우터는 이동하지 않았다.
- Repository는 `app.core`를 import하지 않으며 SQLite·`app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- 무결성 검사 항목·필드·오류 문구 유지.
- 순환 import 없음.

## 테스트

- 변경 전 관련 테스트: `tests/test_v20_database.py`, `tests/test_core.py` — `41 passed in 9.18s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `41 passed in 9.06s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 22.00s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- 무결성 정책 문구와 판정은 Core에 남아 있으므로 검사 기준 변경은 facade와 함께 검토해야 한다.
- `bible_database_dashboard`와 `delete_bible_translation`은 RAG·license·삭제 semantics 때문에 별도 분석이 필요하다.

## Rollback 방법

1. `app/core.py`에 기존 직접 SQL 검사 구현을 복원하고 `fetch_bible_integrity_metrics` import 및 호출을 제거한다.
2. `app/repositories/bible.py`의 helper를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 DATABASE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

`bible_database_dashboard`는 여러 read model을 조합하고, `delete_bible_translation`은 파괴적 작업이므로 즉시 이동하지 않는다. 다음은 Doctrine vector 함수의 raw/Provider 경계를 분석하고 별도 승인한다. Phase 2 Router 분리는 시작하지 않는다.
