# Phase 완료 보고

## 변경 목적

Bible·Doctrine·Project·Sermon 후보 중 낮은 결합의 Project부터 이동하되, Project metadata CRUD만 별도 repository로 분리했다. Dashboard와 workflow가 끌어오는 Sermon/Audit 결합은 이번 범위에서 제외했다.

## 변경 파일

- `app/repositories/project.py` — 신규
- `app/core.py` — `get_project_meta`, `update_project_meta`를 repository에서 re-export

## 변경 내용

- 이동: `get_project_meta`, `update_project_meta`와 `sermon_project_meta` SQL.
- repository는 표준 라이브러리와 `app.paths`만 사용하며 `app.core`, `app.config`, Sermon/Audit/RAG를 import하지 않는다.
- 기존 public 함수명·매개변수·반환 dict·오류 메시지를 유지했다.
- 독립 public 호출을 보존하기 위해 기존과 동일한 `sermons`, `sermon_project_meta` table bootstrap만 제공한다. table/column/schema 정의나 데이터 migration은 변경하지 않았다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema 및 운영 데이터 변경 없음.
- `project_dashboard`와 `sermon_workflow_status`는 core에 남겨 Sermon/Audit 의존성을 새 repository로 확장하지 않았다.
- Bible·Doctrine·Sermon·RAG·NotebookLM·Provider·Router는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v21_backup.py` — `40 passed`
- 변경 후 관련 테스트: 동일 모듈 — `40 passed`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q`
- 결과: `212 passed in 28.44s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `project_dashboard`는 Sermon version, review/audit state, reading speed에 결합되어 있어 Project metadata repository와 분리된 채 core에 남아 있다.
- `sermon_project_meta` bootstrap은 `init_db`에도 유지된다. repository bootstrap은 public metadata API가 독립적으로 호출될 때 기존 동작을 보존하기 위한 최소 중복이다.

## Rollback 방법

1. `app/core.py`에 두 metadata 함수의 기존 구현을 복원한다.
2. repository import를 제거한다.
3. `app/repositories/project.py`를 제거한다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 후보는 Project Dashboard가 아니라, 별도 의존성 분석을 거친 Doctrine 또는 Bible의 가장 작은 CRUD 단위다. 사용자의 다음 승인 전에는 이동하지 않는다.
