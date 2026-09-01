# LM Studio Provider Refactor Plan

## 현재 Provider 경계

`app.core.LMStudioClient`는 다음을 모두 담당한다.

|관심사|현재 동작|보존 요구|
|---|---|---|
|Base URL|기본 `http://127.0.0.1:12345/v1`; legacy `:1234`; `normalize_lmstudio_url`로 localhost·`/v1` 검증|localhost만 허용. `0.0.0.0` 또는 외부 공개 주소로 완화 금지.|
|모델 목록|`GET /v1/models`; 실패 시 native `/api/v1/models` 보조 진단; `lms ps` loaded ID와 교차 확인|OpenAI compatible 결과만 READY 확정으로 취급하는 정책 유지.|
|생성|`POST /v1/chat/completions`; 1회 transport retry 및 catalog 재검증|HTTP/model/context 오류 재시도 금지, transport 끊김만 재시도.|
|Streaming|SSE `stream: true`, `[DONE]`, delta content/text/message 처리|긴 생성의 inactivity timeout 900초, 스트림 종료/빈 결과 오류 유지.|
|reasoning|`delta.reasoning_content`/`delta.reasoning`을 감지하되 결과 텍스트에 섞지 않음|reasoning-only stream이 빈 응답 오류를 내는 현재 가드 유지.|
|embedding|동일 client가 embedding endpoint/응답을 처리하여 RAG/doctrine index가 사용|RAG/doctrine 호출 서명은 그대로 유지.|
|오류 처리|HTTP 400 context-limit을 사용자 조치형 오류로 변환; 연결 실패는 기능 오류|Provider 실패가 FastAPI 서버 종료로 전파되지 않도록 main의 route-level 예외 처리 계약 유지.|
|health/probe|`model_catalog`, `probe_generation`을 preflight/health/recover/start/diagnostics에서 사용|모델 선택, preflight, recovery UI와 테스트 patch 계약 유지.|

## 안전한 이동 순서

### 1. constants.py (선행 조건: baseline 복구 + 승인)

- 이동 후보: `SUPPORTED_SERMON_MINUTES`, `DEFAULT_SERMON_MINUTES`, LM Studio URL 기본/legacy 상수, interpretation/translation 정책 상수 및 정규식.
- 제외: `DB_PATH`의 실제 생성과 SQLite-backed settings 함수.
- 호환: `app.core`에서 같은 이름을 import/re-export한다.
- 검증: 상수 import 및 readiness/preflight 관련 테스트 + 전체 pytest.

### 2. config.py (선행 조건: 1 통과 + 승인)

- 이동 후보: `DB_PATH` 계산, `normalize_lmstudio_url`, `get_lmstudio_url`, `set_lmstudio_url`.
- 주의: 현재 get/set은 `init_db`를 호출한다. 첫 이동에서는 SQL/schema를 새 repository로 옮기지 말고, config가 최소 bootstrap helper를 사용하거나 facade를 통해 기존 구현을 보존해야 한다. `config → core` 역참조는 금지다.
- 호환: `app.core.*` 및 `app.main`의 기존 import/patch 이름을 유지한다.
- 검증: URL 정규화, settings update, LM Studio startup/diagnostics 테스트 + 전체 pytest.

### 3. providers/lmstudio.py (선행 조건: 2 통과 + 승인)

- 이동 대상: `LMStudioClient`와 그 private HTTP/SSE/model-catalog/retry helpers.
- 허용 import: 표준 라이브러리, dataclasses, `app.core.config`, `app.lmstudio_control.loaded_model_ids`.
- 금지 import: `app.core`, RAG, sermon, main, SQLite repositories.
- facade: `app.core`가 `from app.providers.lmstudio import LMStudioClient`로 re-export; main/test patch target은 당분간 유지한다.
- 검증: `test_v32_context_budget.py`, `test_v34_runtime_consistency.py`, `test_v41_lmstudio_startup.py`, `test_v44_streaming_inference.py`, preflight tests, 전체 pytest.

## 중요 위험과 승인 필요 항목

|항목|판정|이유|
|---|---|---|
|테스트 기준선 실패|**승인 전 필수 해결**|`212 passed`가 입증되지 않아 리팩터링 회귀를 판별할 수 없다.|
|Windows SQLite 잠금 조사/테스트 환경 조정|**승인 필요**|테스트 코드, Python 버전, 임시 폴더 또는 DB connection lifecycle에 영향을 줄 수 있다. 이번 분석 범위를 넘어선다.|
|`app.core` compatibility facade 유지|권장|main 및 다수 테스트의 공개 import/patch 계약을 보존한다.|
|provider HTTP 구현 변경|금지|endpoint, timeout, retry, SSE, reasoning_content, 오류 문구 계약을 한 단계에서 바꾸면 안 된다.|

## Rollback 방법

각 실제 단계는 새 파일 추가와 `app/core.py`의 최소 re-export만 포함한다. 관련 테스트가 실패하면 새 모듈 import를 제거하고, 이동 전 `core.py` 구현으로 되돌린다. DB schema, `data/bible.db`, API route, `lmstudio_control.py`, tests는 변경하지 않는다.

## 다음 실행용 명령/프롬프트

```text
먼저 Phase 0 baseline 실패(Windows WinError 32: 임시 test.db 잠금)를 진단하고,
source 변경 없이 전체 pytest가 212 passed 이상인지 재현·확인하라.
테스트 기준선이 확인될 때까지 Phase 1 코드를 수정하지 말라.
기준선이 확인된 경우에만 사용자 승인을 받은 뒤 constants.py 하나만 분리하고,
app.core의 기존 공개 import 경로와 테스트 patch 대상은 유지하라.
```

