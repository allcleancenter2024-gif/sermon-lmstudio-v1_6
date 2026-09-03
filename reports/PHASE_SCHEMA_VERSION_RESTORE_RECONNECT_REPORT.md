# Schema version·restore·adapter 재연결 보고서

## 판정

**조건부 완료**

복원된 테스트 DB에 명시적으로 schema version을 기록하고, 새 PostgreSQL adapter 인스턴스에서 재연결·재조회하는 경로를 자동 검증했다. 운영 DB와 애플리케이션 startup에는 적용하지 않았다.

## 변경 파일

- `app/schema_version.py`
  - 명시적 schema version table 생성
  - idempotent version 기록
  - migration ID 충돌 차단
  - 최신 version 조회
- `tests/test_schema_version.py`
  - SQLite contract 단위 테스트
- `tests/test_schema_version_integration.py`
  - `sermon_db_restore_test` 전용 실제 PostgreSQL 재연결 테스트

## 검증 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| schema version table | PASS | 명시적 helper 호출로 생성 |
| 동일 version 재호출 | PASS | 기존 migration ID 재사용 |
| migration ID 충돌 | PASS | 다른 ID 기록 차단 |
| restore DB version 기록 | PASS | `sermon_db_restore_test`에서 실행 |
| adapter 재연결 | PASS | 새 PostgreSQL adapter 인스턴스 생성 |
| 재연결 후 version 조회 | PASS | `postgres_restore_verified_v1` 확인 |
| 운영 DB 변경 | PASS | 운영 DB 미접근 |
| 앱 startup 자동 변경 | PASS | startup hook 추가 없음 |

## 테스트

- schema version 단위 테스트: `1 passed`
- restore·reconnect 실제 통합시험: `1 passed`
- 전체 회귀: `325 passed, 3 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

전체 회귀의 Skip 3건은 PostgreSQL/MinIO/restore 통합시험을 명시적 플래그 없이 자동 실행하지 않는 안전 게이트다. 각 통합시험은 별도 명시 실행으로 통과했다.

## 안전성

- `sermon_db_test` 백업 원본은 변경하지 않았다.
- 복원 DB `sermon_db_restore_test`에만 schema version metadata를 추가했다.
- 운영 DB·운영 MinIO 변경 없음
- destructive downgrade 없음
- 비밀번호·Secret·연결 문자열 로그 출력 없음
- 잘못된 version 충돌은 fallback 없이 오류 처리

## Rollback

- 새 schema version helper는 startup에서 호출되지 않는다.
- adapter 선택은 기존 `DB_BACKEND=existing` 경로를 유지한다.
- 복원 DB는 별도 테스트 DB이므로 운영 데이터에 영향이 없다.

## 남은 위험

- 운영 schema version 체계는 아직 도입하지 않았다.
- PostgreSQL 전체 애플리케이션 cutover는 검증 대상이 아니다.
- 복원 시간·PITR·백업 보존 정책은 운영 설계가 필요하다.

## 다음 권고

다음 단계는 **테스트 DB에서 migration manifest와 schema version의 일치 여부를 검사하는 read-only drift audit**이다. 운영 DB schema 자동 변경이나 cutover는 별도 승인 전까지 진행하지 않는다.
