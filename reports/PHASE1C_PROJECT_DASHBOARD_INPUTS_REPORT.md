# Phase 완료 보고

## 변경 목적

결합도가 높은 `project_dashboard` 전체를 이동하지 않고, Repository에 dashboard raw 기본 입력 조회 경계만 추가했다. workflow 상태 계산과 최종 응답 조립은 Core에 유지했다.

## 변경 파일

- `app/repositories/project.py` — `fetch_project_dashboard_inputs` 추가
- `app/core.py` — `project_dashboard`가 raw 입력 helper를 사용하도록 변경
- `reports/CORE_DEPENDENCY_MAP.md` — Project dashboard 경계 갱신

## 변경 내용

- Repository helper는 기존 `list_sermons`, `sermon_versions`, `get_project_meta`를 조합해 sermon·latest version·metadata·project metadata를 반환한다.
- Core는 기존대로 `sermon_review_state`, audit/review/lock 상태, `estimate_minutes`, counts와 최종 응답을 계산한다.
- API 반환 구조·필드·상태 값·정렬·SQLite schema와 데이터는 변경하지 않았다.
- `save_sermon`, audit state machine, revision suggestions, Router는 이동하지 않았다.
- Repository는 `app.core`를 import하지 않으며 기존 Project Repository 함수와 표준 라이브러리만 사용한다.

## 기존 기능 영향

- `/api/projects/dashboard` 응답 형식 변경 없음.
- project metadata·version metadata·review/lock/audit 계산 규칙 변경 없음.
- 기존 `app.core.project_dashboard` public 경로 유지.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v34_runtime_consistency.py`, `tests/test_v40_interpretation_flow.py` — `47 passed in 10.41s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `47 passed in 9.88s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 37.47s`

## 발견된 문제

- 없음.

## 남아 있는 위험

- `project_dashboard`는 여전히 workflow/audit read model을 Core에서 조립한다. 이 책임을 이동하려면 audit·review·lock의 불변성 계약을 별도 설계해야 한다.
- helper가 여러 Repository 조회를 조합하므로 향후 성능 최적화나 단일 SQL 변경은 응답 순서·상태에 영향을 줄 수 있다.

## Rollback 방법

1. `app/core.py`에서 `project_dashboard`의 기존 직접 `list_sermons` 루프와 `get_project_meta` 호출을 복원하고 helper import를 제거한다.
2. `app/repositories/project.py`의 `fetch_project_dashboard_inputs`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 PROJECT 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

승인된 순서에 따라 이제 `save_sermon`을 분석한다. 감사·버전 transaction 결합도가 높으면 구현하지 않고 보류 사유와 더 작은 경계를 보고한다. Phase 2 Router 분리는 시작하지 않는다.
