# Phase 3A Router 분리 완료 보고

## 작업 전 Baseline

Git metadata가 없는 작업 디렉터리이며 제품 버전 `40.9.1`, Python `3.14.6`, FastAPI `0.141.1`이다. 전체 pytest 기준선은 **212 passed** (`22.02s`)였다.

## 제품 버전

`app/main.py`의 `APP_VERSION = "40.9.1"`.

## 전체 테스트 Baseline

failed 0, error 0, **212 passed**.

## 기존 main.py 구조

App bootstrap, middleware, lifecycle/init, 69개 OpenAPI path에 해당하는 API endpoint, helper와 import가 하나의 `main.py`에 혼재했다.

## 기존 main.py 라인 수

분리 전 1,615 lines.

## 기존 Route 수

OpenAPI 기준 69 paths(HEAD/OPTIONS 내부 route 포함 시 FastAPI route 객체 수는 별도 집계).

## API Route Snapshot

Health/System 첫 단위의 대상은 `GET /api/runtime`와 `GET /api/health`이며 path, method, 응답 키, status/error 동작을 그대로 보존했다.

## 분리 전략

지시서의 저위험 순서를 따라 Health/System, Settings, Project, Doctrine, Bible, Export Router를 이동하고 각 단계별 테스트와 OpenAPI를 확인했다. Grounding Audit 전용 endpoint, RAG/Sermon/Notebook Router는 아직 이동하지 않았다.

## 생성한 Router

`app/routers/health.py`, `app/routers/settings.py`, `app/routers/projects.py`, `app/routers/doctrine.py`, `app/routers/bible.py`, `app/routers/exports.py`, `app/routers/__init__.py`.

## Router별 Endpoint

- `health_router`: `GET /api/runtime`, `GET /api/health`
- `settings_router`: Settings/LM Studio 6개 endpoint (`/api/settings/*`, `/api/lmstudio/*`)
- `projects_router`: Project/workflow 5개 endpoint (`/api/projects/*`, `/api/workflow/config`, version workflow)
- `doctrine_router`: Doctrine/license/recommend 4개 endpoint
- `bible_router`: 원어 coverage, database dashboard/integrity, reference compare 조회 4개 endpoint
- `bible_router`: passages 단건/일괄 쓰기 endpoint 2개 추가
- `exports_router`: 기존 설교/근거 보고서 Export 및 download 6개 endpoint

## main.py에 유지한 책임

FastAPI app 생성, middleware, startup/init, static mount, template/home, 전역 설정과 나머지 모든 endpoint를 유지했다. `app.include_router(health_router)`만 추가했다.

## 이동한 함수

`runtime_info()`, `health()`, Settings/LM Studio endpoint 8개, Project/workflow endpoint 5개, Doctrine/license/recommend endpoint 4개, Bible 조회 4개 및 쓰기/Import 2개, Export/download 6개 구현.

## 이동하지 않은 함수

Settings, Project, Bible, Doctrine, RAG, Sermon, Grounding, Export, Backup, NotebookLM endpoint와 모든 비즈니스/DB/Provider 로직.

## 변경 파일

- `app/routers/__init__.py`
- `app/routers/health.py`
- `app/main.py`
- `reports/PHASE3A_ROUTER_REFACTOR_REPORT.md`

## 순환 Import 검사

Router는 `app.core`만 참조하고 `app.main`을 import하지 않는다. `main → routers.health → core` 단방향이며 compile/import 검사 통과.

## OpenAPI 비교

분리 후 `/api/runtime`, `/api/health`가 OpenAPI에 존재하며 전체 path 수는 **69**로 확인됐다. response schema/status 변경은 없다.

## Route Count 비교

OpenAPI paths: **69 → 69**. 추가/누락 없음.

## API Path 비교

`/api/runtime`, `/api/health` 모두 동일.

## HTTP Method 비교

두 endpoint 모두 기존 `GET` 유지.

## Request Schema 비교

기존 endpoint에 request body/parameter가 없으며 변경 없음.

## Response Schema 비교

기존 dict key와 값 계산 로직을 그대로 이동했으며 변경 없음.

## Status Code 비교

기존 200 응답 및 health 예외 시 정상 payload 동작 유지.

## SSE/Streaming 영향

이번 단위에서는 Sermon streaming endpoint를 이동하지 않았고 영향 없음.

## Sermon Generation 영향

변경 없음.

## Grounding 영향

변경 없음.

## RAG 영향

변경 없음.

## LM Studio 영향

Health endpoint가 기존과 동일한 Provider public interface를 사용하며 호출 정책 변경 없음.

## Export 영향

변경 없음.

## Backup/Restore 영향

변경 없음.

## DB 영향

schema/data/migration 변경 없음.

## UI 영향

기존 JS API URL 변경 없음.

## Browser Smoke Test

실제 브라우저 실행은 수행하지 않았다. OpenAPI와 관련 endpoint regression으로 대체 검증했다.

## Console 결과

실제 브라우저 Console 검사는 미실행이다.

## Network 오류 결과

기존 route path/method snapshot과 테스트에서 404/405 변경은 확인되지 않았다.

## 성능 영향

Health Router import는 가벼운 core 함수 참조만 수행하며 DB/Provider 초기화를 추가하지 않는다.

## 관련 테스트 결과

Health/Settings/Project/Doctrine/Bible/Export 및 핵심 회귀: **45 passed in 11.74s**.

## 전체 pytest 결과

**212 passed in 22.01s**, failed 0, error 0.

## 발견된 문제

없음. Git status/branch는 repository metadata 부재로 확인할 수 없다.

## 남은 위험

이번 보고서는 Phase 3A 전체가 아니라 Health/System, Settings, Project, Doctrine, Bible, Export Router 단위 완료 보고다. 나머지 Router는 기존 `main.py`에 남아 있으며, 다음 단위마다 별도 OpenAPI/route 비교가 필요하다.

## Rollback 방법

`app.main`의 health router import/include를 제거하고 `runtime_info()`와 `health()`를 기존 위치에 복원하면 된다. DB/API 데이터 rollback은 필요 없다.

## 다음 권장 단계

다음 승인 단위로 Grounding 전용 endpoint 경계를 분석한다. 이후 RAG/Sermon/Notebook 순서로 각 단계별 테스트와 OpenAPI 비교를 수행한다. Web Grounding·새 인증·UI 재설계는 자동 진행하지 않는다.
