# Phase 완료 보고

## 변경 목적

LM Studio OpenAI-compatible HTTP client를 `app/core.py`에서 분리해 provider 경계를 확정하면서, 기존 `app.core.LMStudioClient` 및 테스트 patch 계약을 보존했다.

## 변경 파일

- `app/providers/__init__.py` — 신규
- `app/providers/lmstudio.py` — 신규; LM Studio client 구현 이동
- `app/core.py` — compatibility adapter로 축소
- `reports/CORE_DEPENDENCY_MAP.md` — 현재 provider 경계 반영

## 변경 내용

- 이동: `LMStudioClient`의 URL 초기화, HTTP request, model catalog, `/v1/models`/native fallback, retry, `/v1/chat/completions`, SSE streaming, `reasoning_content` 처리, probe, embeddings.
- provider 의존성: 표준 라이브러리, `app.config`, `app.lmstudio_control`만 사용하며 `app.core`, RAG, sermon, main, SQLite repository를 import하지 않는다.
- `app.core.LMStudioClient`는 provider class를 상속하는 얇은 compatibility adapter다.
- 기존 `app.core.loaded_model_ids` patch 지점을 유지하기 위해 adapter가 provider의 loaded-model resolver만 override한다. `time.sleep`과 `urllib.request.urlopen`은 동일 표준 라이브러리 모듈 객체를 사용하므로 기존 patch target도 유지된다.

## 기존 기능 영향

- localhost-only URL validation, `/v1/models`, `/v1/chat/completions`, model READY 확인, transport-only retry, 900초 inactivity timeout, SSE fallback, `reasoning_content`, context-limit 오류와 기능 단위 오류 격리를 모두 보존했다.
- RAG/doctrine의 `client.embeddings()` 호출 시그니처와 main의 `LMStudioClient` 생성 경로는 변경하지 않았다.
- FastAPI 서버가 LM Studio 장애 때문에 시작/종료되지 않도록 하는 기존 route-level 오류 처리 계약은 변경하지 않았다.

## 테스트

- 관련 테스트: `tests/test_core.py`, `tests/test_v32_context_budget.py`, `tests/test_v34_runtime_consistency.py`, `tests/test_v41_lmstudio_startup.py`, `tests/test_v44_streaming_inference.py` — `56 passed`
- 호환성 검사: `app.core.LMStudioClient`가 provider class를 상속함을 확인
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q`
- 결과: `212 passed in 28.74s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `app.core.LMStudioClient` adapter는 기존 테스트/소비자 호환성을 위해 유지 중이다. 이를 직접 provider import로 바꾸는 작업은 별도 단계와 전용 테스트 검증이 필요하다.
- `app.lmstudio_control`의 Local Server 실행/CLI 제어는 provider HTTP client와 의도적으로 분리된 채 남아 있다.

## Rollback 방법

1. `app/core.py`의 compatibility adapter를 제거하고 원래 `LMStudioClient` 구현을 복원한다.
2. `app/providers/lmstudio.py`와 `app/providers/__init__.py`를 제거한다.
3. 전체 pytest가 `212 passed`인지 확인한다.

DB schema·운영 데이터·API route에는 변경이 없으므로 rollback에 migration은 필요 없다.

## 다음 권장 단계

Phase 1의 허용된 세 소단계가 끝났다. 다음 구조 분리는 DB/RAG/sermon을 함께 이동하지 말고, 별도 승인과 새 Baseline 확인 후 repository 경계를 한 파일씩 계획한다.
