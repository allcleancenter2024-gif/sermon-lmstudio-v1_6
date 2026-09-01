# Phase 완료 보고

## 변경 목적

Bible·원어 데이터의 기본 건수만 집계하는 read-only `db_stats` 책임을 Repository로 분리했다.

## 변경 파일

- `app/repositories/bible.py` — `db_stats` 추가
- `app/core.py` — `db_stats`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — DATABASE 분리 현황 갱신

## 변경 내용

- `passages` 총수, 번역 수, 언어 수, `original_word_notes` 수, `original_lexicon` 수를 기존 SQL과 동일하게 집계한다.
- 기존 반환 키·값 타입·함수명·매개변수를 유지했다.
- 단독 호출 호환성을 위해 관련 기존 table/index bootstrap을 재사용했다.
- `bible_database_dashboard`, `bible_database_integrity`, `delete_bible_translation`, RAG·Doctrine·Project·Sermon·Router는 이동하지 않았다.
- Repository는 `app.core`를 import하지 않으며 SQLite와 `app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- health/status/database API에서 사용하는 `app.core.db_stats` 경로 유지.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v20_database.py`, `tests/test_v40_original_coverage.py` — `51 passed in 9.98s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `51 passed in 10.00s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 22.31s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `db_stats`는 여러 테이블을 집계하므로 table bootstrap/schema 변경과 함께 검토해야 한다.
- 종합 database dashboard와 integrity 검사는 RAG·license·무결성 정책에 결합되어 core에 남아 있다.

## Rollback 방법

1. `app/core.py`에 기존 `db_stats` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/bible.py`의 `db_stats`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 DATABASE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

남은 database dashboard·integrity·삭제 함수는 결합도와 영향 범위가 높으므로, 다음은 Doctrine vector 또는 Bible DB 후보를 다시 분석하고 별도 승인한다. Phase 2 Router 분리는 시작하지 않는다.
