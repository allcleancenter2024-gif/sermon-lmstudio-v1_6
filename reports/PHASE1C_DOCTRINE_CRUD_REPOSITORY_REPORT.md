# Phase 완료 보고

## 변경 목적

Doctrine 영역에서 LM Studio embedding과 검색을 제외한 가장 작은 단위인 doctrine source chunk insert만 repository로 분리했다.

## 변경 파일

- `app/repositories/doctrine.py` — 신규
- `app/core.py` — `add_doctrine_chunk`를 repository에서 re-export

## 변경 내용

- 이동: `add_doctrine_chunk`와 `doctrine_chunks` table/index bootstrap.
- repository는 표준 라이브러리와 `app.paths`만 import하며 `app.core`, provider, RAG, Sermon, main을 import하지 않는다.
- 기존 `app.core.add_doctrine_chunk` public 함수명·인자·반환 ID를 유지했다.
- 기존 `doctrine_chunks` table과 `idx_doctrine_tradition` index 정의를 그대로 사용하며 schema/data migration은 수행하지 않았다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema 및 운영 데이터 변경 없음.
- `build_doctrine_index`와 `doctrine_search`는 LM Studio embeddings·벡터 검색에 결합되어 core에 남아 있다.
- Bible·Project·Sermon·RAG·Router는 변경하지 않았다.

## 테스트

- 사전 관련 테스트: `tests/test_core.py`, `tests/test_v20_database.py`, `tests/test_v29_import_resilience.py` — `44 passed`
- 변경 후 doctrine 관련 테스트: `tests/test_core.py`, `tests/test_e2e_v6.py` — `35 passed`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q`
- 결과: `212 passed in 67.51s`

## 발견된 문제

- pytest 실행 프로세스의 종료 신호가 도구에 늦게 수집됐지만, 임시 로그의 최종 pytest 요약은 정상 통과를 확인했다.

## 남아 있는 위험

- Doctrine index/search의 Provider·vector 의존성은 아직 core에 남아 있다.
- doctrine table bootstrap은 `init_db`에도 남아 있으며, repository bootstrap은 독립 public API 호출의 기존 동작을 보존하기 위한 최소 중복이다.

## Rollback 방법

1. `app/core.py`에 기존 `add_doctrine_chunk` 구현을 복원한다.
2. repository import를 제거한다.
3. `app/repositories/doctrine.py`를 제거한다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 후보는 Bible의 translation-license CRUD(`register_translation_license`, `translation_licenses`)다. 본문 import/RAG invalidation을 포함하지 않는 독립 단위이므로, 별도 사용자 승인 후에만 진행한다.
