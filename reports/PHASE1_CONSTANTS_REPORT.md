# Phase 완료 보고

## 변경 목적

`app/core.py`에 섞여 있던 순수 상수와 정규식을 dependency-free 모듈로 분리해, 다음 `config.py`와 `providers/lmstudio.py` 단계가 `app.core`를 역참조하지 않도록 기반을 마련했다.

`app/core.py`가 현재 단일 파일이므로 `app/core/constants.py` 디렉터리를 추가하면 `app.core` 모듈 경로와 충돌할 위험이 있다. 따라서 안전한 실제 목적지는 `app/constants.py`로 정했다.

## 변경 파일

- `app/constants.py` — 신규
- `app/core.py` — 상수를 import/re-export하도록 최소 변경

## 변경 내용

- 이동: 설교 시간, LM Studio URL 기본값/legacy 값, 번역·해석 흐름 정책, 사회 맥락/인용/품질 정규식, review 상태 상수.
- `app/constants.py`는 표준 라이브러리 `re`만 import한다.
- `app.core`는 같은 심볼을 import하므로 기존 `from app.core import DEFAULT_SERMON_MINUTES` 등 공개 import 경로와 `app.main`/테스트 소비자는 바뀌지 않는다.
- `DB_PATH`, URL 정규화·저장, SQLite 접근, `LMStudioClient`, RAG, Prompt 생성, FastAPI 라우트는 이동하지 않았다.

## 기존 기능 영향

- 기능 동작 변경 없음.
- `app.constants`는 `app.core`를 import하지 않고, `app.core → app.constants` 단방향만 존재한다. config/provider와의 순환 참조를 만들지 않는다.

## 테스트

- 관련 테스트: `tests/test_core.py`, `tests/test_v40_social_neutrality.py`, `tests/test_v40_translation_policy.py` — `44 passed`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q`
- 결과: `212 passed in 28.68s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음. 기준선 복구 단계에서 정리한 SQLite 명시적 connection close가 그대로 유지되며, constants 분리 후에도 전체 테스트가 통과했다.

## 남아 있는 위험

- `app.core`를 직접 patch하는 기존 테스트 계약을 유지해야 한다.
- 다음 config 단계에서 `get_lmstudio_url`/`set_lmstudio_url`가 현재 `init_db`에 의존한다. `config → core` 역참조가 생기지 않도록 settings persistence 경계를 별도로 설계해야 한다.

## Rollback 방법

1. `app/core.py`의 constants import를 제거하고 이동한 정의를 원래 위치로 복원한다.
2. `app/constants.py`를 제거한다.
3. 전체 pytest가 다시 `212 passed`인지 확인한다.

DB schema·운영 데이터·API route에는 변경이 없으므로 rollback에 데이터 migration은 필요 없다.

## 다음 권장 단계

사용자 승인 후 `config.py`만 분리한다. `DB_PATH`, `normalize_lmstudio_url`, `get_lmstudio_url`, `set_lmstudio_url`의 기존 `app.core` 공개 경로는 compatibility re-export로 보존하고, LM Studio provider 이동은 그 다음 별도 단계로 제한한다.
