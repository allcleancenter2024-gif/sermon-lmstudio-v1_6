# Schema version 기록·재백업·재복원 보고서

## 판정

**조건부 완료**

원본 테스트 DB `sermon_db_test`에 manifest와 일치하는 schema version을 명시적으로 기록하고, 새 백업을 생성해 `sermon_db_restore_test_v2`로 복원했다. 두 DB 모두 read-only drift audit에서 PASS를 확인했다.

## 실행 범위

- 변경 대상: `sermon_db_test`의 schema metadata만
- 백업 대상: `sermon_db_test`
- 복원 대상: `sermon_db_restore_test_v2`
- 기존 복원 DB `sermon_db_restore_test`: 유지
- 운영 DB `sermon_db`: 미접근
- 운영 MinIO: 미접근

## 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| 원본 test DB version 기록 | PASS | version 1, manifest migration ID 기록 |
| 재백업 | PASS | PostgreSQL custom-format dump 생성 |
| 신규 복원 DB 생성 | PASS | `sermon_db_restore_test_v2` |
| 신규 복원 | PASS | `pg_restore --exit-on-error` 성공 |
| 원본 drift audit | PASS | 필수 테이블·확장·version 일치 |
| 복원 drift audit | PASS | 필수 테이블·확장·version 일치 |
| 새 adapter 재연결 | PASS | 복원 DB에서 새 인스턴스가 version 재조회 |
| 운영 데이터 보호 | PASS | 운영 DB·MinIO 변경 없음 |

## Version 정보

- version: `1`
- migration ID: `postgres_restore_verified_v1`
- required extension: `vector`

## 테스트

- 전체 회귀: `327 passed, 4 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS
- read-only drift audit: 원본·복원 모두 PASS

전체 회귀의 Skip 4건은 PostgreSQL·MinIO 통합시험에 명시적 환경변수가 없을 때 자동 실행을 막는 안전 게이트다.

## 안전성 및 rollback

- 운영 DB migration/cutover 없음
- 운영 MinIO 변경 없음
- 기존 SQLite DB 변경 없음
- 복원 대상 DB 삭제·초기화 없음
- backup 파일과 기존·신규 restore DB를 유지해 재현 가능
- 새 metadata 기록은 테스트 DB에만 적용됐으며, 운영 전환과 무관함

## 남은 위험

- schema version 1은 테스트용 manifest 기준이며 운영 migration manifest가 아니다.
- 운영 전환 전에는 운영용 backup 보존·복원 시간·PITR 정책을 별도로 검증해야 한다.
- 전체 애플리케이션 PostgreSQL cutover는 여전히 수행하지 않았다.

## 다음 권고

다음 단계는 **운영 전환 전 조건 점검표를 테스트 환경에서 자동 산출하는 readiness audit**이다. 결과가 PASS가 아니면 운영 전환을 진행하지 않는다.
