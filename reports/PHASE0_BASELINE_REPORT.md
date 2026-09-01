# PHASE 0 Baseline Report

## 기준 버전

- 제품 버전: `40.9.1` (`VERSION.txt`, `app/main.py`)
- 작업 디렉터리: `C:\Users\Home_care\Desktop\Bible_Speak\sermon-lmstudio-v1_6`
- Git: 이 디렉터리와 상위 경로에서 `.git`을 찾지 못했다. 따라서 현재 브랜치와 사전 변경 목록은 확인할 수 없다.
- 분석 범위: `CODEX_REFACTOR_INSTRUCTIONS.md`만 리팩터링 작업지시로 사용했다. Phase 1 리팩터링은 수행하지 않았다.

## 현재 구조

```text
app/
  core.py                # SQLite, 성경/설교 도메인, RAG, Prompt, LM Studio Client가 공존
  main.py                # FastAPI 앱, 요청 모델, 모든 API 라우트와 orchestration
  backup.py              # backup/restore
  exporters.py           # DOCX/PDF/HTML/package 출력
  importers.py           # 성경/원어 import 변환
  lmstudio_control.py    # lms CLI 및 localhost 서버 제어
  notebooklm.py          # NotebookLM 연구노트/팩
  paths.py, references.py
tests/                   # 38개 테스트 모듈
data/bible.db            # SQLite 운영 데이터
```

## 최초 Baseline 테스트 결과

명령: `python -m pytest -q`

- 결과: 실패. 최초 실행에서 다수 실패 표식이 출력되었고, 실패 원인을 분리하기 위해 `python -m pytest -q -x`를 실행했다.
- 첫 실패: `tests/test_core.py::CoreTests::test_audit_warnings_block_approval`
- 실패 위치: 테스트 `tearDown`의 `TemporaryDirectory.cleanup()`
- 오류: `PermissionError: [WinError 32] ... CreatorTemp\\...\\test.db`
- 판정: 임시 SQLite DB 파일이 다른 프로세스 또는 열린 연결에 의해 잠겨 삭제되지 않았다. 해당 실패만으로 기능 결함인지, Windows/ESTsoft CreatorTemp 환경의 외부 잠금인지 확정할 수 없다.
- 기대 기준: `212 passed`
- 최초 판정: **미충족**. 이후 승인된 기준선 복구를 수행했다.

## 승인된 진단 결과 (소스 변경 없음)

- `TMPDIR`를 `CreatorTemp`에서 사용자 Temp로 프로세스 한정 변경해도 동일한 `WinError 32`가 재현되었다. 따라서 임시 폴더 자체 또는 외부 ESTsoft 프로세스만의 문제는 아니다.
- 시스템 Python은 `3.14.5`이며 `pytest`는 있지만 `python-docx`가 없어 DOCX 관련 테스트가 별도로 실패한다.
- 프로젝트 `.venv`는 Python `3.14.6`, `python-docx`는 설치되어 있으나 `pytest`가 설치되어 있지 않다. 따라서 현재 어느 실행 환경도 `requirements.txt`와 테스트 도구를 함께 만족하지 않는다.
- `.venv`에서 `unittest tests.test_core`를 실행하면 `ResourceWarning: unclosed database in <sqlite3.Connection ...>`가 대량 발생하고, 같은 테스트 DB 삭제가 실패한다.
- 직접 원인: `app/core.py`(및 `app/notebooklm.py`)가 광범위하게 `with sqlite3.connect(...) as con:`만 사용한다. SQLite Connection context manager는 commit/rollback을 수행할 뿐 `close()`를 호출하지 않는다. Python 3.14/Windows에서는 남은 connection handle이 `TemporaryDirectory.cleanup()`의 DB 파일 삭제를 막는다.
- 부수 원인: baseline 실행에 사용한 시스템 Python에는 `python-docx`가 없다. `test_core`의 두 DOCX 테스트는 `RuntimeError: Word 출력 모듈 python-docx가 설치되지 않았습니다.`로 실패한다.

### 기준선 복구에 필요한 별도 작업

1. 모든 SQLite connection lifecycle을 명시적으로 닫도록 최소 수정한다(예: `contextlib.closing(sqlite3.connect(...))` 또는 `try/finally: con.close()`). 이는 기능 변경이지만 Phase 1 분리 전 선행되어야 하는 버그 수정이다.
2. 하나의 명시적 개발 환경에 `requirements.txt` 및 test runner(`pytest`)를 함께 설치한다. 현재 `.venv`에는 runtime 의존성은 있으나 `pytest`가 없다.
3. 관련 test_core와 전체 pytest를 다시 실행하여 `212 passed` 이상을 확인한다.

이 선행 수정은 `constants.py → config.py → providers/lmstudio.py` 분리와 별개다.

## 승인된 기준선 복구 및 최종 검증

### 변경 파일

- `app/core.py`: `_connect()` context helper 추가. 기존 모든 SQLite 접근이 transaction commit/rollback 뒤 `close()`되도록 변경.
- `app/notebooklm.py`: 동일한 `_connect()` helper 및 SQLite 접근 변경.
- `tests/test_core.py`, `tests/test_v21_backup.py`, `tests/test_v29_import_resilience.py`, `tests/test_v40_notebooklm_bridge.py`: 테스트가 직접 연 SQLite connection을 transaction 종료 후 명시적으로 닫도록 변경.
- 프로젝트 `.venv`: runtime 의존성이 이미 있는 환경에 `pytest`를 설치.

### 보존한 동작

- SQLite transaction의 기존 commit/rollback 의미를 유지했다. 첫 시도에서 close만 적용해 commit이 사라지는 회귀를 발견했고, 즉시 transaction과 close를 함께 보장하는 helper로 정정했다.
- DB schema, `data/bible.db`, API route, LM Studio 설정/endpoint, RAG/sermon/prompt 동작은 변경하지 않았다.

### 최종 테스트 결과

명령: `.\\.venv\\Scripts\\python.exe -m pytest -q`

```text
212 passed in 28.51s
PYTEST_EXIT=0
```

최종 판정: **충족**. 기준선 테스트가 `212 passed`로 확인되었으므로, 사용자 승인 시에만 Phase 1의 첫 작은 단위인 `constants.py` 분리를 제안·수행할 수 있다.

## 가장 위험한 결합

1. `app/core.py`는 설정/SQLite/도메인/RAG/Prompt/LM Studio HTTP client를 동시에 소유한다.
2. `app/main.py`는 `app.core`의 60개 이상 심볼을 직접 import하고, `LMStudioClient`를 직접 생성한다. 기존 테스트도 `app.main.LMStudioClient`와 `app.core.urllib.request.urlopen`을 patch한다.
3. LM Studio URL 설정은 SQLite `settings` 테이블에서 읽지만, URL 정규화와 HTTP client가 같은 `core.py`에 있다.
4. 테스트 기준선이 현재 실패하므로, 모듈 이동으로 새 회귀와 기존 환경 문제를 분리할 수 없다.

## 안전하게 먼저 분리할 코드 (조건부)

테스트 기준선 복구 후에도 아래 순서만 허용한다.

1. `app/core/constants.py`: 순수 상수와 정규식만 이동하고 `core.py`에서 재-export한다.
2. `app/core/config.py`: `DB_PATH`, LM Studio URL 상수, URL 정규화와 settings 접근을 이동하되, 기존 `app.core` 공개 심볼은 호환 re-export한다.
3. `app/providers/lmstudio.py`: `LMStudioClient`만 이동하고, RAG/sermon 함수의 client 인자 방식은 유지한다.

## 지금 이동하면 안 되는 코드

- `init_db` 및 모든 SQLite schema/데이터 접근 함수
- RAG index/search 및 doctrine embedding 함수
- evidence packet, prompt, sermon 생성/품질/audit/workflow 함수
- `app/main.py` 라우트와 `app/lmstudio_control.py`의 서버 실행 제어
- backup/restore, importer, exporter, NotebookLM 경계

## Rollback 계획

- 이번 단계에서는 SQLite resource-lifecycle 수정과 위에 기록한 테스트 수정이 추가되었으며, 운영 데이터와 DB schema에는 변경이 없다.
- 다음 단계에서는 각 작은 이동 전 Git 또는 동등한 파일 스냅샷을 확보하고, 이전 `app.core` import 경로를 re-export로 유지한다.
- 실패 시 새 모듈 추가와 최소 import 변경만 되돌리고 `core.py`의 원래 구현을 즉시 복원한다. DB schema·데이터·backup 파일은 건드리지 않는다.

## 다음 실행 허용 조건

- `.venv`에서 `python -m pytest -q`가 `212 passed` 이상을 보고할 것 (**충족**)
- `CORE_DEPENDENCY_MAP.md`의 cycle 완화 규칙을 수용할 것
- `LMSTUDIO_PROVIDER_REFACTOR_PLAN.md`의 provider 경계를 수용할 것
- 실제 파일 변경 전 사용자 승인 획득
