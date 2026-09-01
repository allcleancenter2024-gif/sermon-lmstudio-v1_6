# Phase 1D Sermon Service 완료 보고

## 작업 전 Baseline

Git metadata가 없는 디렉터리이며 제품 버전 후보는 `sermon-lmstudio-final-package-v40`이다. 전체 기준선은 **212 passed**, failed/error 0 (`21.89s`)였다.

## 기존 Sermon Generation 구조

`app/main.py::generate_sermon` endpoint가 research 수집, outline 정리, LM Studio 호출, resize, 인용/품질 검증, audit 생성과 응답 조립을 모두 수행했다.

## Generation Workflow

이번 이동 전후 순서는 동일하다: 모델 선택 → Prompt 구성 → 1차 생성(컨텍스트 초과 시 compact 재시도) → duration resize(최대 2회) → quote/citation 검증 → post-generation quality → generation audit → API 응답 조립.

## 이동한 함수

`app/services/sermon_service.py::generate_sermon_workflow`를 추가하고 위 생성 후처리 orchestration을 이동했다.

## 이동하지 않은 함수

Research packet 수집(`_collect_research_packet`), 본문/outline 사전 처리, Router endpoint, Repository 구현, Prompt 문자열, RAG/ Grounding 알고리즘, Provider HTTP 구현, Export/UI는 이동·변경하지 않았다.

## Service 책임

주입된 client와 helper를 사용해 생성 workflow 순서, resize, validation, audit 호출 및 결과 조립을 담당한다. DB SQL이나 HTTP 구현은 소유하지 않는다.

## Repository 책임

이전 Phase에서 분리한 `app.repositories.sermon.persist_sermon_version`이 저장을 담당한다. 이번 단계에서 Repository schema/API는 변경하지 않았다.

## LM Studio Provider 경계

Service는 `client.chat()` public interface만 호출하며 URL, timeout, streaming, reasoning, model 선택 정책은 변경하지 않았다.

## RAG 경계

검색 및 doctrine 조회는 기존 `main`/core 흐름에서 수행한다. Service는 이미 준비된 passages를 전달받는다.

## Grounding 경계

기존 grounding/evidence 결과와 정책을 그대로 사용하며 validator나 알고리즘을 새로 구현하지 않았다.

## Prompt 경계

기존 `build_sermon_prompt`, `build_resize_prompt`를 동일한 인자와 순서로 호출했다. Prompt 텍스트는 변경하지 않았다.

## core.py Compatibility Wrapper

기존 `core.generate_sermon` public facade는 없었으므로 `main.py`의 기존 `/api/sermons` endpoint를 유지했다. `core.save_sermon` 및 기존 public interface도 그대로 유지된다.

## 변경 파일

- `app/services/sermon_service.py`
- `app/main.py`
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE1D_SERMON_SERVICE_REPORT.md`

## API 영향

URL, method, request/response schema, status code, error format, endpoint 위치 변경 없음. 기존 응답의 `research_packet`은 endpoint에서 동일하게 추가한다.

## DB 영향

SQLite schema, 데이터, audit 저장 방식 변경 없음. Service는 직접 DB에 접근하지 않는다.

## Generation 결과 영향

기존 생성·resize·검증·audit 순서와 반환 필드를 유지했다.

## LM Studio 호출 횟수 비교

정상 생성 1회, 컨텍스트 초과 시 기존 compact 재시도 1회, resize 조건 충족 시 기존 최대 2회라는 호출 상한을 그대로 유지했다. 중복 호출을 추가하지 않았다.

## 성능 영향

동일한 helper와 SQL/Provider 호출을 사용하므로 의도된 추가 RAG, Grounding, DB, LM 호출은 없다.

## 순환 Import 검사

`sermon_service.py`는 `app.main`을 import하지 않는다. Service → core helper 방향만 존재하며 `core`는 Service를 import하지 않아 순환이 없다. compile/import 검사 통과.

## 관련 테스트 결과

생성·Evidence·Preflight·Quality·Repository·Export 회귀 묶음: **71 passed** (`15.91s`).

## 전체 pytest 결과

**212 passed in 29.87s**, failed 0, error 0.

## 추가 테스트

별도 테스트 파일은 추가하지 않았다. 기존 회귀 세트로 workflow 결과와 호출 경계를 검증했다.

## 발견된 문제

없음. Git status/branch는 저장소 metadata 부재로 확인할 수 없었다.

## 남은 위험

Research packet 수집과 outline 전처리는 여전히 `main.py`/core에 있어 Service 분리는 부분적이다. 후속 확장 시 private helper 의존성을 독립 모듈로 정리해야 한다.

## Rollback 방법

`main.py`에서 `generate_sermon_workflow(...)` 호출 블록을 이전 inline orchestration으로 복원하고 Service import 및 파일을 제거한다. DB migration이 없으므로 데이터 rollback은 필요 없다.

## 다음 권장 단계

이번 Phase 1D 범위에서 중단한다. 다음 단계는 별도 승인 후 남은 Sermon orchestration 경계를 분석하며, RAG/FTS5/RRF/Grounding Validator/Prompt/Router 분리는 자동 수행하지 않는다.
