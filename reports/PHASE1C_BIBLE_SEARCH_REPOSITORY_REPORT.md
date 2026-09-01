# Phase 완료 보고

## 변경 목적

Bible 영역에서 등록 본문을 token 기반으로 검색하는 read-only SQL 책임만 Repository로 분리했다.

## 변경 파일

- `app/repositories/bible.py` — `search_passages` 및 기존 passage table bootstrap 재사용
- `app/core.py` — `search_passages`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — Bible 분리 현황 갱신

## 변경 내용

- 이동: query whitespace tokenization, 최대 8 token OR 조건, reference/text LIKE 검색, limit, reference·translation 정렬.
- 기존 public 함수명·매개변수·기본 limit·빈 query 반환·반환 필드를 유지했다.
- RAG·reference expansion·comparison·research 로직은 이동하지 않았다. RAG가 호출하는 검색 public 경로만 호환 re-export로 유지했다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리·`app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- `app.core.search_passages` 기존 import 경로 유지.
- Bible import, Doctrine·Project·Sermon·RAG index/search·Provider·Router 코드는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py`, `tests/test_v20_database.py` — `42 passed in 11.37s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `42 passed in 10.10s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 23.14s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `search_passages`는 RAG 및 본문 비교의 입력이므로 검색 결과 의미를 바꾸는 SQL 변경은 후속 단계에서 별도 승인해야 한다.
- `init_db`와 Repository 양쪽에 passage table bootstrap이 남아 있다. 기존 public 함수의 독립 호출 호환성을 위한 제한된 중복이다.

## Rollback 방법

1. `app/core.py`에 기존 `search_passages` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/bible.py`의 `search_passages`와 `re` import를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 BIBLE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 후보는 `compare_reference`처럼 reference expansion과 다중 번역 정렬을 포함하는 함수로 결합도가 상승한다. 구현 전 의존성·API 영향 분석과 별도 승인을 먼저 진행한다. Phase 2 Router 분리는 시작하지 않는다.
