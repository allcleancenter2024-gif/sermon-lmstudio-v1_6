# doctrine_processing chunk repository 연결 보고서

## 판정

**조건부 완료 — chunk 저장 contract 연결**

`doctrine_processing`의 chunk 삭제·일괄 삽입·조회 로직을 `DoctrineChunkRepository`로 분리하고, 기존 SQLite processing 경로와 PostgreSQL 테스트 adapter에서 동일한 결과를 검증했다.

## 변경 파일

- `app/doctrine_repository_contract.py`
  - `DoctrineChunkRepository.replace_chunks()`
  - `DoctrineChunkRepository.list_chunks()`
- `app/doctrine_backend.py`
  - chunk repository factory 연결
- `app/doctrine_processing.py`
  - 기존 SQLite chunk 저장을 repository contract 경유로 변경
- `scripts/postgres_doctrine_chunks_schema.sql`
  - 테스트 DB additive chunk schema
- 관련 테스트 파일

## 결과

| 항목 | 결과 |
|---|---|
| 기존 SQLite chunk 처리 | PASS |
| PostgreSQL chunk replace | PASS |
| PostgreSQL chunk list | PASS |
| JSONB scripture refs/topic tags | PASS |
| chunk 순서 보존 | PASS |
| document foreign key 연결 | PASS |
| transaction rollback | PASS |
| 운영 DB 접근 | 없음 |
| 운영 MinIO 변경 | 없음 |

## 발견 및 수정

PostgreSQL psycopg는 connection 객체에 `executemany`를 제공하지 않고 cursor에서 제공한다는 API 차이가 실제 통합시험에서 발견됐다. cursor 기반 batch insert로 수정했다.

또한 PostgreSQL 테스트 schema에는 chunk table이 없어 additive test-only schema를 추가하고 `sermon_db_test`, `sermon_db_restore_test_v2`에만 적용했다.

## 테스트

- 관련 processing/contract 테스트: `5 passed`
- 실제 PostgreSQL chunk 통합시험: `1 passed`
- 전체 회귀: `338 passed, 10 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

## 안전성

- 기존 SQLite가 기본 backend
- PostgreSQL fixture는 transaction rollback
- 운영 DB와 운영 MinIO 미접근
- chunk schema는 테스트 DB에만 additive 적용
- 자동 cutover와 기존 schema 삭제 없음
- Secret·비밀번호·연결 문자열 미출력

## 남은 위험

- `doctrine_processing`의 document 조회와 review status 갱신은 아직 SQLite 직접 접근이다.
- doctrine workflow·RAG·embedding repository는 다음 별도 단계다.
- PostgreSQL schema migration 전체와 운영 cutover는 검증하지 않았다.

## Rollback

- 기존 processing 함수는 기본 SQLite adapter를 사용한다.
- 새 chunk repository 파일과 연결부를 되돌려도 기존 DB 데이터는 삭제되지 않는다.
- 테스트 fixture는 rollback되어 남지 않았다.

## 다음 권고

다음 단계는 `doctrine_processing`의 document 조회와 review status 갱신을 동일한 factory 경계에 연결하는 것이다. 기존 SQLite를 기본값으로 유지하고 PostgreSQL은 테스트 DB에서만 검증한다.
