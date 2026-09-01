# Phase 완료 보고

## 변경 목적

`bible_database_dashboard`의 번역별 raw 집계와 RAG vector count 조회만 Repository로 분리하고, Core의 `db_stats`·`rag_stats` 결합 및 최종 응답 조립은 유지했다.

## 변경 파일

- `app/repositories/bible.py` — `fetch_bible_dashboard_rows` 추가
- `app/core.py` — `bible_database_dashboard`가 raw rows helper를 사용하도록 변경
- `reports/CORE_DEPENDENCY_MAP.md` — DATABASE dashboard 경계 갱신

## 변경 내용

- Repository가 기존 passages/license JOIN, translation별 passages·references·characters 집계, allow_fulltext/license_status, translation별 RAG vector count를 조회한다.
- Core는 기존대로 `db_stats`, `rag_stats`를 호출하고 `database`·`rag`·`translations` 응답을 조립한다.
- 기존 정렬·필드·값 타입·API 응답 구조를 유지했다.
- integrity·삭제 함수, RAG index/search, Doctrine·Project·Sermon·Router는 이동하지 않았다.

## 기존 기능 영향

- `/api/database/dashboard`와 import/delete 후 dashboard 응답 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- 순환 import 없음.

## 테스트

- 변경 전 관련 테스트: `tests/test_v20_database.py`, `tests/test_core.py` — `41 passed in 9.98s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `41 passed in 9.25s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 22.56s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- dashboard는 `db_stats`·`rag_stats`와 결합된 read model이며, 향후 통계 필드 변경은 세 함수의 계약을 함께 검토해야 한다.
- `delete_bible_translation`은 파괴적 동작과 RAG 삭제를 수행하므로 별도 transaction·rollback 검증 없이는 이동하지 않는다.

## Rollback 방법

1. `app/core.py`에서 기존 dashboard SQL과 vector count loop를 복원하고 helper import를 제거한다.
2. `app/repositories/bible.py`의 `fetch_bible_dashboard_rows`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 DATABASE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음은 Doctrine vector read/persist 경계까지 분리된 상태를 유지한다. `delete_bible_translation`은 삭제 승인과 rollback 검증이 필요하므로 즉시 진행하지 않고, 별도 분석·승인을 먼저 받는다. Phase 2 Router 분리는 시작하지 않는다.
