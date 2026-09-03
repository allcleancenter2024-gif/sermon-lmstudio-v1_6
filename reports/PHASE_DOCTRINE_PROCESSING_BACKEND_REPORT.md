# doctrine_processing backend 연결 보고서

## 판정

**조건부 완료 — 문서 metadata 경계 연결**

`doctrine_processing` 전체를 한 번에 전환하지 않고, 문서 metadata read/update만 doctrine backend factory를 통해 선택할 수 있도록 연결했다. 기본 실행 경로는 기존 SQLite이며, PostgreSQL은 명시적으로 주입된 테스트 adapter에서만 사용된다.

## 변경 내용

- `read_document_processing_metadata()` 추가
- `write_document_processing_metadata()` 추가
- 동일 transaction connection 주입 지원
- 기존 `process_doctrine_document()`의 기본 SQLite 동작 보존
- PostgreSQL metadata read/update 실제 통합시험 추가

## 결과

| 항목 | 결과 |
|---|---|
| SQLite metadata read | PASS |
| SQLite metadata write | PASS |
| PostgreSQL metadata read | PASS |
| PostgreSQL metadata write | PASS |
| JSON/JSONB round-trip | PASS |
| 동일 transaction 일관성 | PASS |
| fixture rollback | PASS |
| 기존 chunk 처리 회귀 | PASS |
| 운영 DB 접근 | 없음 |

## 테스트

- 관련 SQLite processing 테스트: `4 passed`
- 실제 PostgreSQL metadata 통합시험: `1 passed`
- 전체 회귀: `338 passed, 9 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

전체 회귀의 Skip 9건은 외부 통합시험을 명시적 환경변수 없이 자동 실행하지 않는 안전 게이트다.

## 안전성

- 기존 `snapshot_source`, chunk insert, RAG, workflow 경로는 자동 전환하지 않았다.
- PostgreSQL fixture는 동일 transaction에서 rollback했다.
- 운영 DB·운영 MinIO 미접근
- 기존 SQLite adapter와 기본 실행 경로 보존
- Secret·비밀번호·연결 문자열 미출력

## 발견된 설계 보완

초기 구현에서 helper가 내부적으로 새 연결을 열면 외부 transaction의 미commit fixture를 읽지 못할 수 있었다. 선택적 `connection` 주입을 추가해 transaction 경계를 호출자가 명확히 제어하도록 보완했다.

## 남은 위험

- `doctrine_processing`의 chunk 저장은 아직 SQLite 직접 접근이다.
- 문서 review status, chunk repository, workflow/RAG의 PostgreSQL 전환은 남아 있다.
- 전체 애플리케이션 cutover는 검증되지 않았다.

## Rollback

- backend 인자를 전달하지 않으면 기존 SQLite metadata 경로를 사용한다.
- 새 helper를 되돌려도 기존 DB·MinIO 데이터에는 영향이 없다.

## 다음 권고

다음 단계는 `doctrine_processing`의 chunk 저장 repository를 별도 contract로 분리하는 것이다. 문서 metadata 경계와 동일하게 SQLite 기본값을 유지하고, PostgreSQL은 테스트 DB에서만 검증한다.
