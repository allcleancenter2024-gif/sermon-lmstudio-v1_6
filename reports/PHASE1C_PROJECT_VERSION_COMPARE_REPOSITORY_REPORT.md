# Phase 완료 보고

## 변경 목적

Project 영역에서 저장된 두 설교 버전의 unified diff를 계산하는 read-only 책임만 Repository로 분리했다.

## 변경 파일

- `app/repositories/project.py` — `compare_sermon_versions` 및 `difflib` 의존성 추가
- `app/core.py` — `compare_sermon_versions`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — Project 분리 현황 갱신

## 변경 내용

- 이동: 분리된 `sermon_versions` 조회 결과에서 두 버전을 선택하고 unified diff를 생성하는 로직.
- 기존 public 함수명·매개변수·누락 버전 오류 메시지·diff 헤더/형식을 유지했다.
- DB 쓰기, 감사 연결, Provider, RAG, Router 의존성은 추가하지 않았다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리와 기존 Project Repository 함수만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- `app.core.compare_sermon_versions` 기존 import 경로 유지.
- `save_sermon`, 감사 상태 머신, revision suggestions, Project dashboard는 이동하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py` — `35 passed in 10.40s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `35 passed in 10.48s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 25.28s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `save_sermon`은 version 생성과 generation audit 연결을 한 transaction에서 처리하므로 별도 분석·승인 없이는 이동하지 않는다.
- `compare_sermon_versions`는 `sermon_versions` Repository 함수에 결합된 작은 read-only 계층이다.

## Rollback 방법

1. `app/core.py`에 기존 `compare_sermon_versions` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/project.py`의 함수와 `difflib` import를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 PROJECT 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

Project의 남은 `save_sermon`은 감사·버전 결합도가 높아 보류한다. 다음은 Bible/Doctrine의 남은 단일 CRUD 또는 해당 보류 사유를 유지하는 방향을 의존성 지도와 함께 다시 승인받는다. Phase 2 Router 분리는 시작하지 않는다.
