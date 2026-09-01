# Phase 완료 보고

## 변경 목적

Project 영역에서 특정 설교의 저장 버전 목록을 읽고 metadata JSON을 복원하는 단일 조회 책임만 Repository로 분리했다.

## 변경 파일

- `app/repositories/project.py` — `sermon_versions` 및 기존 sermon table bootstrap 재사용
- `app/core.py` — `sermon_versions`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — Project 분리 현황 갱신

## 변경 내용

- 이동: `sermon_versions(sermon_id, db_path)`의 SQLite 조회, 최신순 정렬, `metadata_json` JSON 변환.
- 기존 public 함수명·매개변수·반환 필드·정렬 순서를 유지했다.
- `list_sermons` 단계에서 정의한 기존 `sermons`·`sermon_versions` table bootstrap을 재사용했다.
- `save_sermon`, `compare_sermon_versions`, 감사 연결 및 Project dashboard는 이동하지 않았다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리·`app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- `app.core.sermon_versions` 기존 import 경로 유지.
- Bible·Doctrine·Sermon 생성·RAG·Provider·Router 코드는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py` — `35 passed in 10.51s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `35 passed in 10.31s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 24.15s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `save_sermon`은 버전 생성·감사 연결·metadata 정제까지 포함하므로 이번 단계에서 이동하지 않았다.
- `init_db`와 Repository 양쪽에 sermon table bootstrap이 남아 있다. 기존 public 함수의 독립 호출 호환성을 위한 제한된 중복이다.

## Rollback 방법

1. `app/core.py`에 기존 `sermon_versions` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/project.py`의 `sermon_versions` 추가분을 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 PROJECT 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 단계는 `save_sermon`의 감사·버전 결합도를 먼저 분석해야 한다. 결합도가 높으면 Project Repository 이동을 잠시 중단하고, Bible/Doctrine의 남은 단일 CRUD를 비교한다. Phase 2 Router 분리는 시작하지 않는다.
