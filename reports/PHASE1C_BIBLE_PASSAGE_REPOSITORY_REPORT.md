# Phase 완료 보고

## 변경 목적

Bible 영역에서 번역본 사용권 등록부와 직접 결합된 단일 본문 저장 책임만 `app/repositories/bible.py`로 분리했다. import, 본문 검색·비교, 연구 패킷, RAG 생성·검색은 이동하지 않았다.

## 변경 파일

- `app/repositories/bible.py` — `add_passage` 및 해당 테이블 bootstrap 추가
- `app/core.py` — `add_passage`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — Bible 분리 현황 및 모듈 그래프 갱신

## 변경 내용

- 이동: `add_passage`의 translation license guard, passages upsert, 기존 RAG embedding 삭제.
- 기존 public 함수명·매개변수 순서·기본값·예외 메시지와 SQLite upsert SQL을 유지했다.
- `add_passage` 단독 호출도 기존처럼 동작하도록 passages, translation_licenses, rag_embeddings table bootstrap을 repository에 최소 범위로 둔다.
- RAG의 생성·조회 알고리즘은 이동하지 않았다. 이 단계에서의 RAG 관련 책임은 본문 변경 뒤 이미 존재하던 embedding 행 삭제뿐이다.
- repository는 표준 라이브러리와 `app.paths`만 import하며 `app.core`를 import하지 않는다. 의존 방향은 `core facade -> repositories.bible -> paths/SQLite`여서 순환 import가 없다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- 기존 SQLite table명·columns·data migration 변경 없음.
- `app.core.add_passage`가 re-export로 계속 제공되어 main과 테스트의 기존 import 경로를 유지한다.
- `import_json`, `import_items`, reference search/comparison, Bible research, RAG index/search, Doctrine·Project·Sermon·Router는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v20_database.py`, `tests/test_v23_original_language.py`, `tests/test_v25_evidence_guards.py` — `55 passed in 18.28s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `55 passed in 14.58s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 24.69s`

## 발견된 문제

- `add_passage`는 단순 upsert가 아니라 기존 RAG embedding 무효화도 수행한다. 이를 삭제하거나 다른 계층으로 미루면 기존 동작이 달라지므로, 해당 단일 SQL 삭제를 함께 보존했다.

## 남아 있는 위험

- `init_db`에도 동일 테이블 bootstrap이 남아 있다. public 함수의 독립 호출 호환성을 위한 제한된 중복이며, 스키마를 변경하지 않는다.
- 대량 import와 RAG lifecycle은 여전히 core에 있어, 다음 단계에서는 분리 범위를 더 작게 분석·승인해야 한다.

## Rollback 방법

1. `app/core.py`에 이전 `add_passage` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/bible.py`에서 `add_passage`와 `_ensure_passage_tables`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 Bible 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 후보는 Bible 영역의 개별 조회 함수 또는 Project/Sermon의 독립 CRUD 중 실제 의존도가 가장 낮은 하나를 다시 지도화한 뒤, 별도 승인을 받아 진행한다. Phase 2 Router 분리는 시작하지 않는다.
