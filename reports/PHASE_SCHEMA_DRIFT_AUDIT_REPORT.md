# PostgreSQL schema manifest drift audit 보고서

## 판정

**조건부 완료**

schema manifest와 현재 테스트 DB schema를 변경 없이 비교하는 read-only audit를 추가하고 실행했다. 복원 DB는 PASS였고, 원본 테스트 DB는 schema version 기록 누락으로 DRIFT를 정확히 보고했다.

## 변경 파일

- `scripts/postgres_schema_manifest.json`
- `app/schema_drift_audit.py`
- `tests/test_schema_drift_audit.py`
- `tests/test_schema_drift_integration.py`

## Manifest 기준

- version: `1`
- migration ID: `postgres_restore_verified_v1`
- 필수 테이블: 교단·출처·문서·snapshot·ingestion job·object metadata·schema version
- 필수 확장: `vector`

## 실제 결과

| 대상 | 결과 | 세부 내용 |
|---|---|---|
| `sermon_db_test` | DRIFT | `schema_versions` table 및 version 기록 없음 |
| `sermon_db_restore_test` | PASS | 필수 테이블·`vector`·version 1·migration ID 일치 |
| 운영 DB `sermon_db` | 미접근 | 운영 schema 변경 방지 |

원본 테스트 DB에 version을 자동 삽입해 PASS로 만드는 작업은 read-only audit 범위를 벗어나므로 수행하지 않았다.

## 테스트

- drift audit 단위 테스트: `3 passed`
- 복원 DB 실제 audit: `1 passed`
- 전체 회귀: `327 passed, 4 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

전체 회귀의 Skip 4건은 PostgreSQL·MinIO·schema restore 통합시험을 명시적 환경변수 없이 자동 실행하지 않는 안전 게이트다.

## 안전성

- audit는 `SELECT`만 수행했다.
- `CREATE`, `ALTER`, `INSERT`, `DELETE`, `DROP` 없음
- 운영 DB·운영 MinIO 미접근
- 원본 테스트 DB도 변경 없음
- version mismatch를 fallback이나 자동 수정으로 덮지 않음

## 위험과 권고

- 원본 테스트 DB에 schema version metadata가 없어 manifest 기준 DRIFT다.
- 다음 migration 적용 시 version table을 명시적으로 기록한 뒤 backup을 다시 생성해야 한다.
- 운영 전환 전에는 모든 대상 DB가 PASS인지 확인해야 하며, DRIFT 상태에서는 cutover하지 않는다.

## Rollback

이번 단계는 read-only이므로 DB rollback이 필요 없다. 추가된 manifest·audit 코드와 테스트를 되돌려도 DB 데이터에는 영향이 없다.

## 다음 권고

다음 한 단계는 **원본 `sermon_db_test`에 대한 명시적 schema version migration 기록과 재백업·재복원 검증**이다. 이 작업은 테스트 DB에만 수행하고, 운영 DB migration은 별도 승인 전까지 진행하지 않는다.
