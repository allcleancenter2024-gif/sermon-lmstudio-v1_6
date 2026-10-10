# Project Dashboard / Workflow 경계 계약

작성일: 2026-09-30  
제품 버전: 40.9.10  
범위: `app/application/project_facade.py`, `app/repositories/project.py`, `app/core.py`, `app/routers/projects.py`

## 1. 구조 점검 결과

새로운 구조적 blocker는 발견되지 않았다. repository 입력과 workflow 계산에 이어, 이번 단계에서 dashboard 응답 조합을 순수 presenter 경계로 이동했다.

기존 보존 규칙:

- SQLite schema 변경 없음
- `/api/projects/dashboard`, `/api/project-summary`, `/api/workflow/config`, `/api/sermons/{sermon_id}/versions/{version}/workflow` URL 변경 없음
- workflow 상태명과 step key 변경 없음
- audit·review·lock·SHA-256 무결성 계산을 우회하지 않음
- legacy `app.core` import 경로는 당장 제거하지 않음

## 2. 호출 graph

```text
HTTP request
  └─ app/routers/projects.py
       └─ app/application/project_facade.py
            ├─ dashboard()
            │    ├─ app/repositories/project.py::fetch_project_dashboard_inputs(db_path)
            │    └─ app/services/project_dashboard_presenter.py::compose_project_dashboard()
            │         ├─ app/repositories/project.py::fetch_project_dashboard_inputs(db_path)
            │         │    ├─ list_sermons()
            │         │    ├─ sermon_versions()
            │         │    └─ get_project_meta()
            │         ├─ app/core.py::sermon_review_state()
            │         │    ├─ sermon_review_history()
            │         │    ├─ sermon_version_lock()
            │         │    └─ audit_for_version()
            │         └─ app/services/project_dashboard_presenter.py::compose_project_dashboard()
            │              └─ response composition: projects + summary + reading_cpm
            │
            └─ workflow(sermon_id, version)
                 └─ app/services/project_workflow_service.py::build_workflow_status()
                      ├─ app/repositories/project.py::sermon_versions()
                      ├─ app/core.py::sermon_review_state()
                      ├─ audit/review/lock records
                      └─ response composition: 7 steps + completed + next_step + locked
```

## 3. 책임 경계

| 경계 | 현재 책임 | 계약 | 다음 분리 후보 |
|---|---|---|---|
| Repository input | 프로젝트·버전·metadata 조회 | DB row를 dict로 반환하고 source 내용을 변경하지 않음 | `ProjectDashboardInput` 모델 |
| Workflow calculation | audit·review·lock에서 단계 상태 계산 | `completed`, `next_step`, `locked`, 7개 고정 step key 유지 | `workflow_service.py` 순수 계산 함수 |
| Response composition | `project_dashboard_presenter.py`에서 dashboard 응답 조합 | 기존 JSON key와 상태 문자열 유지 | typed input model 검토 |
| Application facade | router에 안정된 호출 entry 제공 | 예외를 router가 HTTP 404/400으로 매핑할 수 있게 전달 | repository/service 조합만 보유 |
| Router | URL·HTTP status·auth boundary | 기존 URL과 error mapping 유지 | `main.py` 호환 route와 별도 검증 |

## 4. 외부 contract

### Dashboard

`GET /api/projects/dashboard`

- top-level: `projects`, `summary`, `reading_cpm`
- project row: `sermon_id`, `topic`, `latest_version`, `service_date`, `series_name`, `preacher`, `notes`, `state`, `audit_status`, `locked`, `target_minutes`, `minutes_estimate`, `reading_cpm`, `updated_at`
- summary: `total`, `unreviewed`, `comment`, `changes_requested`, `approved`, `locked`

### Workflow

`GET /api/sermons/{sermon_id}/versions/{version}/workflow`

- top-level: `sermon_id`, `version`, `steps`, `completed`, `next_step`, `locked`
- step count: 7
- fixed keys: `brief`, `bible`, `languages`, `draft`, `evidence`, `review`, `final`
- statuses: `completed`, `attention`, `pending`
- missing version: application raises `ValueError`, router maps it to HTTP 404

## 5. 이번 단계에서 실행한 분리

`app/services/project_workflow_service.py::build_workflow_status()`를 추가했다.

- service는 `app.core`, `FastAPI`, SQLite를 import하지 않는다.
- `load_versions`와 `load_review_state` callback으로 persistence·review 경계를 주입받는다.
- 기존 `app.core.sermon_workflow_status()`는 동일한 함수명과 인자를 유지하는 compatibility wrapper가 된다.
- 기존 7개 step key, status, `completed`, `next_step`, `locked` 응답을 유지한다.
- workflow 계산은 기존 audit·review·lock 결과를 그대로 사용하며 새로운 저장 상태를 만들지 않는다.

`app/services/project_dashboard_presenter.py::compose_project_dashboard()`도 추가했다.

- presenter는 `app.core`, `FastAPI`, SQLite를 import하지 않는다.
- repository가 준비한 dashboard input, 기존 review-state loader, 기존 duration estimator를 callback과 인자로 주입받는다.
- `app.core.project_dashboard()`는 기존 함수명·인자를 유지하는 compatibility wrapper가 된다.
- project row와 summary의 기존 key, 상태 문자열, reading CPM 동작을 유지한다.
- 데이터베이스 없이 presenter contract를 검증하는 단위 테스트를 추가했다.

`app/application/project_facade.py`가 두 순수 경계를 직접 조합하도록 변경했다.

- `dashboard()`는 repository input → review-state callback → dashboard presenter 순서로 조합한다.
- `workflow()`는 repository의 `sermon_versions()`와 기존 review-state callback을 workflow service에 주입한다.
- `core.py`의 `project_dashboard()`와 `sermon_workflow_status()`는 legacy import 호환을 위해 유지한다.
- router URL, HTTP error mapping, DB schema, UI 응답 key는 변경하지 않았다.
- facade 조합 계약을 정적 테스트로 고정했다.

## 6. 안전한 다음 구현 순서

1. `ProjectDashboardInput` TypedDict를 바탕으로 repository 입력의 nested field를 더 세분화하되 dict 반환 호환성을 유지한다.
2. health router의 runtime TestClient 계약을 추가하고 LM Studio 장애 응답을 고정한다.
3. settings/projects router도 실제 HTTP status와 auth middleware 조합을 TestClient로 검증한다.
4. 관련 contract와 전체 회귀 테스트를 통과한 뒤에만 기존 core compatibility wrapper의 내부 의존성 축소를 검토한다.

## 9. Typed repository input 계약

`app/repositories/project.py`에 `ProjectDashboardInput(TypedDict)`를 추가했다.

- repository가 반환하는 네 개의 경계를 명시한다: `sermon`, `version`, `version_item`, `project`
- 실제 반환값은 기존과 같은 `dict`이며 DB schema나 API 응답은 변경하지 않는다.
- `fetch_project_dashboard_inputs()`의 반환 annotation을 `list[ProjectDashboardInput]`으로 고정했다.
- 전체 테스트 결과: `451 passed, 19 skipped, 1 warning`

## 10. Health runtime 계약 검증

`tests/test_router_contracts.py`에 health 실행 계약을 추가했다.

- `/api/runtime`의 local runtime identity와 localhost LM Studio URL 확인
- 모델 catalog 정상 응답에서 `connected`, `models`, `database`, `rag`, `message` 확인
- LM Studio `ConnectionError` 발생 시 degraded response가 유지되는지 확인
- 실제 LM Studio와 운영 DB에는 연결하지 않고 client·repository 통계를 대체해 테스트

전체 테스트 결과: `454 passed, 19 skipped, 1 warning`.

## 11. Settings runtime 계약 검증

`tests/test_router_contracts.py`에 settings 실행 계약을 추가했다.

- reading speed 허용 범위 `180~600`과 저장 응답 확인
- LM Studio localhost 설정의 정상 catalog 응답 확인
- LM Studio 연결 실패가 HTTP 오류가 아닌 비치명적 degraded response로 유지되는지 확인
- 잘못된 LM Studio 주소가 HTTP 400으로 매핑되는지 확인
- 실제 설정 DB와 LM Studio 서버에는 연결하지 않고 의존성을 대체해 테스트

전체 테스트 결과: `457 passed, 19 skipped, 1 warning`.

## 12. Projects runtime 및 auth 계약 검증

`tests/test_router_contracts.py`에 projects 실행 계약을 추가했다.

- dashboard·summary·workflow config가 facade 응답을 그대로 전달하는지 확인
- workflow와 project detail의 `ValueError → HTTP 404` 매핑 확인
- metadata 저장의 정상 응답, `ProjectValidationError → HTTP 400`, `ValueError → HTTP 404` 확인
- `main.py` middleware의 공개 경로와 인증 필요 경로를 현재 동작 그대로 고정
- `/api/runtime`과 auth endpoint는 공개이며 `/api/health`를 포함한 나머지 데이터 API는 인증이 필요함을 확인

구조적으로 확인된 주의점: 현재 `/api/health`는 이름과 달리 middleware 공개 경로에 포함되지 않아 인증이 필요하다. 런처가 `/api/runtime`을 사용하므로 기능 오류로 단정하지 않았으며, 공개 health가 필요하다면 별도 승인과 client 흐름 검토 후 변경해야 한다.

전체 테스트 결과: `461 passed, 19 skipped, 1 warning`.

## 13. Assembled HTTP contract 검증

`tests/test_http_router_contracts.py`를 추가해 실제 `app.main.app`를 ASGI로 읽기 호출했다.

- `/api/runtime`: HTTP 200, runtime identity, app version, localhost LM Studio URL 확인
- `/api/auth/status`: HTTP 200 및 인증 상태 응답 key 확인
- `/api/health`, `/api/projects/dashboard`, `/api/project-summary`: 미인증 HTTP 401과 `auth_required` JSON 확인
- TestClient가 요구하는 `httpx2`가 개발 환경에 없어 의존성을 설치하지 않고 최소 ASGI harness를 사용
- 쓰기 endpoint와 계정 변경은 호출하지 않음

추가 관찰: 인증 실패는 middleware의 조기 반환으로 처리되므로 `X-Sermon-App-Version` header가 붙지 않는다. 현재 동작을 보존하고 테스트에 반영했으며, header 일관성을 개선하려면 별도 middleware 변경과 회귀 검증이 필요하다.

전체 테스트 결과: `463 passed, 19 skipped, 1 warning`.

## 7. 이번 단계에서 하지 않은 것

- `core.py` 전면 이동
- dashboard/workflow API 응답 변경
- DB schema 변경 또는 migration
- audit/review/lock 계산 복제
- router URL 변경
- UI의 workflow step key 변경

## 8. 전체 구조 점검 및 router 계약 고정

전체 import/call 경계를 다시 점검한 결과, 즉시 중단할 구조적 blocker는 발견되지 않았다. 다만 다음 잔여 위험은 확인되었다.

- `app/core.py`가 여전히 많은 repository·provider·RAG 기능을 함께 import하는 큰 compatibility 중심 모듈이다.
- `app/main.py`가 앱 생성 외에도 다수의 legacy handler와 기능 import를 보유하고 있다.
- `health.py`는 DB/RAG 통계와 LM Studio 상태를 한 응답에서 조합하므로 provider 장애와 저장소 상태를 별도 service로 옮길 때 계약 보존이 필요하다.
- 인증은 router 내부가 아니라 `main.py` HTTP middleware에서 공통 적용된다. 따라서 router만 분리할 때도 공개 경로 목록과 `401` JSON 계약을 함께 보존해야 한다.

이번 단계에서는 전면 분리 대신 `tests/test_router_contracts.py`를 추가했다.

- health runtime/health URL과 주요 response key 고정
- settings URL, 입력 범위, HTTP 400 매핑, LM Studio localhost 기본값 고정
- projects URL, workflow key, HTTP 400/404 매핑 고정
- `main.py`를 import하지 않고 source contract를 검사하여 테스트가 production DB를 초기화하지 않도록 함

검증 결과: `451 passed, 19 skipped, 1 warning`.

다음 단계는 typed repository input model을 도입하거나, router를 실제로 `main.py`에서 한 개씩 분리하는 것이다. 실제 router 이동은 각 endpoint의 runtime TestClient 계약을 추가한 뒤 진행해야 한다.
