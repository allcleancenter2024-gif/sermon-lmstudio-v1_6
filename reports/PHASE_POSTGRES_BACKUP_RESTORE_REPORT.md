# PostgreSQL 테스트 DB 백업·복원 보고서

## 판정

**조건부 완료**

운영 DB가 아닌 `sermon_db_test`를 custom-format으로 백업하고, 별도 `sermon_db_restore_test`에 복원해 schema·행 수·관계·핵심 metadata 정합성을 검증했다.

## 실행 범위

- 백업 원본: `sermon_db_test`
- 복원 대상: `sermon_db_restore_test`
- 운영 DB `sermon_db`: 접근·변경 없음
- 백업 형식: PostgreSQL custom format
- schema 삭제·초기화: 수행하지 않음
- 운영 데이터 전체 복사: 수행하지 않음

## 검증 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| `pg_dump` 실행 | PASS | PostgreSQL 16.15 custom dump 생성 |
| 백업 파일 유효성 | PASS | 비어 있지 않은 dump 파일 확인 |
| 별도 복원 DB 생성 | PASS | `sermon_db_restore_test` 생성 |
| `pg_restore` 실행 | PASS | `--exit-on-error` 성공 |
| `vector` 확장 | PASS | 원본·복원 DB 모두 활성화 |
| 테이블 행 수 | PASS | 원본·복원 모두 교단 1, 출처 1, 객체 metadata 1 |
| 외래키 정합성 | PASS | 원본·복원 모두 고아 참조 0건 |
| 필수 컬럼 | PASS | 원본·복원 모두 NULL 필수값 0건 |
| 핵심 필드 비교 | PASS | 교단·출처·object key·version ID·SHA-256·크기·상태 동일 |
| 기존 SQLite 보존 | PASS | SQLite 원본 및 애플리케이션 경로 변경 없음 |

## 백업·복원 절차

1. `sermon_db_test`만 `pg_dump -Fc`로 백업했다.
2. 별도 이름의 `sermon_db_restore_test`를 만들었다.
3. `pg_restore --exit-on-error`로 복원했다.
4. 원본과 복원 DB의 확장, 행 수, 외래키 및 핵심 필드를 비교했다.

백업 파일은 로컬 임시 디렉터리에 유지하며, 복원 DB도 후속 재현을 위해 유지한다. 삭제 작업은 수행하지 않았다.

## 발견된 환경 이슈와 처리

- Compose PostgreSQL 이미지에는 `postgres` role이 없었고 `sermon_user`가 관리 role이었다. 실제 role 권한을 확인한 후 `sermon_user`로 복원했다.
- Windows Docker CLI에서 `docker cp -LiteralPath`가 지원되지 않아 경로 옵션을 수정했다.
- 위 오류들은 데이터 변경 전에 발생했으며, 재실행은 성공했다.

## 남은 위험

- 운영 DB의 backup/restore는 안전상 실행하지 않았다.
- 실제 운영 전환을 위한 PITR, 보존 기간, 암호화 저장, 복원 시간 목표는 별도 운영 설계가 필요하다.
- schema downgrade는 destructive 가능성이 있어 실행하지 않았다.

## Rollback

- 이번 단계는 원본 테스트 DB를 변경하지 않았다.
- 복원 DB와 백업 파일을 유지하므로 재검증이 가능하다.
- 운영 전환은 수행되지 않았으므로 기존 SQLite 경로와 운영 환경은 그대로다.

## 다음 권고

다음 한 단계는 **테스트 DB에서 schema version 기록과 restore 후 adapter 재연결을 자동화하는 검증**이다. 운영 DB migration이나 cutover는 별도 승인 전까지 수행하지 않는다.
