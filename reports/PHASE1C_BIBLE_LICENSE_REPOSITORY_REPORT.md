# Phase 완료 보고

## 변경 목적

Bible 영역에서 본문 import/RAG를 건드리지 않고, 가장 낮은 결합 단위인 번역본 사용권 등록·조회만 repository로 분리했다.

## 변경 파일

- `app/repositories/bible.py` — 신규
- `app/core.py` — `register_translation_license`, `translation_licenses`를 repository에서 re-export

## 변경 내용

- 이동: `register_translation_license`, `translation_licenses`와 `translation_licenses` table bootstrap.
- 기존 table명, columns, upsert 규칙, 정렬 순서, 반환 dict, public 함수명을 유지했다.
- repository는 표준 라이브러리와 `app.paths`만 import하며 core/config/RAG/Sermon/main을 import하지 않는다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema 및 운영 데이터 변경 없음.
- `add_passage`, `import_items`, reference comparison, RAG vector invalidation은 core에 남아 있다.
- Doctrine·Project·Sermon·Provider·Router는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v20_database.py`, `tests/test_v29_import_resilience.py`, `tests/test_v19_import_wizard.py` — `49 passed`
- 변경 후 관련 테스트: 동일 모듈 — `49 passed`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q`
- 결과: `212 passed in 28.69s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- 본문 import는 translation license, passages, rag embeddings를 함께 다루므로 아직 core에 남아 있다.
- license table bootstrap은 `init_db`에도 유지되며 repository bootstrap은 기존 public API의 독립 호출 동작을 보존하기 위한 최소 중복이다.

## Rollback 방법

1. `app/core.py`에 기존 license 함수 구현을 복원한다.
2. repository import를 제거한다.
3. `app/repositories/bible.py`를 제거한다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 Bible 후보는 `add_passage` 하나다. import/RAG invalidation을 제외한 단순 본문 upsert와 license guard만 이동하는 별도 승인 단위로 제한한다.
