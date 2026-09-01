# Phase 완료 보고

## 변경 목적

`app/core.py`와 `app/config.py`에 있던 `app_settings` SQLite 접근을 `Settings Repository`로 옮겨 Settings 책임만 분리했다. Bible·Sermon·Doctrine·RAG·Router는 범위에서 제외했다.

## 변경 파일

- `app/repositories/__init__.py` — 신규
- `app/repositories/settings.py` — 신규
- `app/config.py` — URL 설정 정책은 유지하고 Settings SQL을 repository로 위임
- `app/core.py` — 읽기 속도 Settings public API를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — Settings 경계 갱신

## 이전 구조

```text
app.core
  ├─ get_reading_cpm / set_reading_cpm / calibrate_reading_cpm
  └─ app_settings SQL

app.config
  └─ LM Studio URL get/set + app_settings SQL/bootstrap
```

## 새 구조

```text
app.core ───────────────→ app.repositories.settings
app.config ─────────────→ app.repositories.settings
app.repositories.settings → app.paths + SQLite + 표준 라이브러리
```

`app.repositories.settings`는 `app.core`와 `app.config`를 import하지 않으므로 순환 import가 없다.

## 변경 내용

- repository가 기존 `app_settings` 테이블의 bootstrap, JSON 읽기/쓰기, reading CPM get/set/calibrate를 소유한다.
- `app.config`는 기존 `get_lmstudio_url`/`set_lmstudio_url`/localhost validation/legacy 포트 migration 정책을 유지하고 repository의 JSON persistence만 사용한다.
- `app.core`는 기존 `get_reading_cpm`/`set_reading_cpm`/`calibrate_reading_cpm` 공개 이름을 그대로 re-export한다.
- table명, column명, key (`reading_cpm`, `lmstudio_url`), JSON 저장 형식과 DB schema는 변경하지 않았다.

## 기존 기능 영향

- API URL과 request/response 형식 변경 없음.
- SQLite schema와 운영 데이터 변경 없음.
- `app.main`과 기존 테스트의 Settings import 경로를 변경하지 않았다.
- LM Studio Provider, Bible, Sermon, Doctrine, RAG, Backup/Restore 및 Phase 2 Router는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v34_runtime_consistency.py`, `tests/test_v41_lmstudio_startup.py` — `48 passed`
- 변경 후 호환성 검사: core/config public Settings API, temporary SQLite DB, repository JSON persistence — 통과
- 변경 후 관련 테스트: 동일 세 모듈 — `48 passed`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q`
- 결과: `212 passed in 28.18s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `init_db`에도 기존 `app_settings` schema 선언이 남아 있다. 이는 schema 소유권을 유지하기 위한 것으로, repository bootstrap은 독립 호출 시 기존 table이 없는 DB에서도 Settings public API를 안전하게 동작시키기 위한 최소 보장이다.
- NotebookLM의 drive-folder persistence는 같은 `app_settings` 테이블을 직접 사용하지만, 이번 Settings Repository 범위에는 포함하지 않았다. 이를 이동하려면 별도 승인과 전용 테스트가 필요하다.

## Rollback 방법

1. `app/core.py`에 reading CPM 구현과 SQL을 복원한다.
2. `app/config.py`에 기존 URL Settings SQL/bootstrap을 복원한다.
3. `app/repositories/settings.py`와 `app/repositories/__init__.py`를 제거한다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

이번 승인 범위는 여기서 종료한다. 다음 Repository 후보(Bible, Sermon, Doctrine) 또는 NotebookLM Settings migration은 별도 의존성 분석과 사용자 승인을 받은 뒤 한 단위씩 진행한다. Phase 2 Router 분리는 시작하지 않는다.
