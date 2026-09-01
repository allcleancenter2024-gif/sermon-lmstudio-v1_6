# Phase 완료 보고

## 변경 목적

Project 영역에서 설교 목록의 최신 버전 번호를 읽는 단순 read-only 책임만 Repository로 분리했다.

## 변경 파일

- `app/repositories/project.py` — `list_sermons` 및 조회에 필요한 기존 table bootstrap 추가
- `app/core.py` — `list_sermons`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — Project 분리 현황 갱신

## 변경 내용

- 이동: `sermons`와 `sermon_versions`를 JOIN해 설교별 최신 version을 반환하는 조회.
- 기존 public 함수명·매개변수·반환 dict 필드·정렬 순서를 유지했다.
- 단독 호출 호환성을 위해 기존 `sermons`·`sermon_versions` table 정의를 Repository에 보장했다.
- `save_sermon`, `sermon_versions`, 버전 비교, 감사 연결 및 Project dashboard는 이동하지 않았다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리·`app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- `app.core.list_sermons` 기존 import 경로 유지.
- Bible·Doctrine·Sermon·RAG·Provider·Router 코드는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py` — `35 passed in 10.48s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `35 passed in 10.53s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 24.61s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `init_db`와 Repository 양쪽에 sermon table bootstrap이 남아 있다. 기존 public 함수의 독립 호출 호환성을 위한 제한된 중복이다.
- 설교 저장·버전·감사 흐름은 서로 결합되어 있으므로 이번 단계에서 이동하지 않았다.

## Rollback 방법

1. `app/core.py`에 기존 `list_sermons` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/project.py`의 `list_sermons`와 `_ensure_sermon_list_tables`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 PROJECT 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 단계는 `sermon_versions` 또는 `save_sermon`의 감사 결합 여부를 먼저 재분석해야 한다. 독립성이 낮다고 판단되면 Project에서 더 진행하지 않고 Bible/Doctrine의 남은 단일 CRUD를 비교한다. Phase 2 Router 분리는 시작하지 않는다.
