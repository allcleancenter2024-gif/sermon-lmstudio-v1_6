# Phase 완료 보고

## 변경 목적

LM Studio 로컬 URL 설정 경계를 `app/core.py`에서 분리해, 다음 provider 모듈이 core를 import하지 않고 설정을 사용할 수 있도록 했다.

## 변경 파일

- `app/config.py` — 신규
- `app/core.py` — config 공개 심볼 import/re-export 및 기존 구현 제거

## 변경 내용

- 이동: `DB_PATH`, `normalize_lmstudio_url`, `get_lmstudio_url`, `set_lmstudio_url`.
- `app.config`는 `app.constants`, `app.paths`, 표준 라이브러리만 import하며 `app.core`·RAG·provider·main을 import하지 않는다.
- 설정 모듈은 독립적으로 `app_settings` 테이블을 보장하고, commit/rollback 후 SQLite connection을 닫는다.
- URL 계약 유지: localhost (`127.0.0.1`, `localhost`, `::1`) HTTP와 `/v1`만 허용, 계정정보/query/fragment 거부, 환경변수 우선, legacy `:1234` 설정의 `:12345` 마이그레이션.
- `app.core`가 같은 이름을 re-export하므로 기존 `app.main` 및 테스트의 import/patch 계약은 유지된다.

## 기존 기능 영향

- LM Studio URL 저장/조회와 기존 오류 메시지의 동작을 보존했다.
- DB schema, RAG, sermon/prompt, provider HTTP client, FastAPI routes는 이동 또는 변경하지 않았다.
- 의존 방향: `core → config → {constants, paths}`. `config → core` 역참조가 없어 import cycle이 없다.

## 테스트

- 관련 테스트: `tests/test_core.py`, `tests/test_v34_runtime_consistency.py`, `tests/test_v41_lmstudio_startup.py` — `48 passed`
- 호환성 검사: `app.config`와 `app.core`의 `DB_PATH`·URL normalizer 동일성, 임시 SQLite DB의 저장/조회 통과
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q`
- 결과: `212 passed in 29.03s`

## 발견된 문제

- pytest 실시간 출력이 도구 응답에서 일부 누락됐다. 임시 로그 `C:\\Users\\Home_care\\AppData\\Local\\Temp\\sermon_phase1_config_pytest.txt`의 최종 요약으로 결과를 확인했다.

## 남아 있는 위험

- `app_settings` 테이블 bootstrap이 현재 `init_db`와 `app.config._ensure_settings_table`에 각각 존재한다. schema 소유권은 후속 repository 단계에서 통합할 대상이며, 이번 단계에서는 순환 참조를 피하기 위해 의도적으로 중복을 제한했다.
- `LMStudioClient`는 아직 `app.core`에 있어 provider boundary가 완성되지 않았다.

## Rollback 방법

1. `app/core.py`에 `DB_PATH`와 URL 설정 구현을 복원한다.
2. config import를 제거한다.
3. `app/config.py`를 제거한다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB schema·운영 데이터·API route에는 변경이 없으므로 rollback에 migration은 필요 없다.

## 다음 권장 단계

사용자 승인 후 `app/providers/lmstudio.py`만 분리한다. HTTP/SSE/model catalog/retry/embedding/probe 구현을 이동하되, `app.core.LMStudioClient` re-export와 기존 테스트 patch target은 유지한다.
