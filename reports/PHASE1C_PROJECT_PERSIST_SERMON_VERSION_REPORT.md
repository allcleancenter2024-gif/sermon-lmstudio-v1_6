# Phase 완료 보고

## 변경 목적

`save_sermon`의 버전 저장·audit 연결 transaction을 Project Repository로 이동하고, public `app.core.save_sermon`은 호환 facade로 유지했다.

## 변경 파일

- `app/repositories/project.py` — `persist_sermon_version` 및 저장에 필요한 기존 table bootstrap 추가
- `app/core.py` — `save_sermon`이 Repository transaction 함수를 호출하도록 변경
- `reports/CORE_DEPENDENCY_MAP.md` — Project 저장 경계 갱신

## 변경 내용

- Repository가 sermon 생성/존재 확인, 다음 version 계산, metadata JSON 직렬화, audit 미연결 여부 확인, version INSERT, audit 연결 UPDATE를 하나의 transaction으로 소유한다.
- 기존 audit 연결 조건과 invalid audit metadata 정제(`audit_id`, `audit`, `review_state` 제거)를 그대로 유지했다.
- `app.core.save_sermon` 함수명·서명·반환 필드·오류 메시지를 유지하는 얇은 facade로 변경했다.
- 기존 table명·columns와 schema를 변경하지 않았다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리·`app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- 기존 sermon/version/audit transaction 원자성 유지.
- 감사·review·lock state machine, revision suggestions, dashboard 조립은 변경하지 않았다.
- Phase 2 Router 분리 미착수.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py`, `tests/test_v40_interpretation_flow.py` — `42 passed in 10.14s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `42 passed in 9.64s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 22.22s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- audit 연결 정책이 Repository transaction 안으로 이동했으므로, 향후 audit schema/상태 조건 변경은 `persist_sermon_version`과 함께 검토해야 한다.
- `init_db`와 Repository 양쪽에 sermon/audit table bootstrap이 남아 있다. 기존 public 함수 독립 호출 호환성을 위한 제한된 중복이다.

## Rollback 방법

1. `app/core.py`에 이전 `save_sermon` 구현을 복원하고 `persist_sermon_version` import를 제거한다.
2. `app/repositories/project.py`의 `persist_sermon_version` 및 저장 bootstrap 추가분을 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 PROJECT 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

`project_dashboard`의 workflow state 계산은 여전히 Core에 남아 있으며, audit/review/lock 결합도가 높다. 다음 단계는 이를 즉시 이동하지 말고 후보를 다시 분석한 뒤 별도 승인한다. Phase 2 Router 분리는 시작하지 않는다.
