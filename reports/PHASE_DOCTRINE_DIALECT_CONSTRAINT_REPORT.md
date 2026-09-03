# Doctrine timestamp·JSONB·constraint 회귀 보고서

## 판정

**조건부 완료**

동일 doctrine fixture에 대해 SQLite와 PostgreSQL의 timestamp, JSON/JSONB metadata, foreign key 및 unique constraint 동작을 비교했다. 운영 DB와 운영 애플리케이션 경로는 변경하지 않았다.

## 결과

| 항목 | SQLite | PostgreSQL | 판정 |
|---|---|---|---|
| timestamp 저장·조회 | 문자열 값 | timezone-aware datetime | PASS, 의미 보존 확인 |
| JSON metadata round-trip | JSON text encode/decode | JSONB encode/decode | PASS |
| unique 위반 | 정규화 오류 | 정규화 오류 | PASS |
| foreign key 위반 | 정규화 오류 | 정규화 오류 | PASS |
| transaction 복구 | rollback 가능 | savepoint rollback 후 계속 가능 | PASS |
| 운영 데이터 | 변경 없음 | 운영 DB 미접근 | PASS |

## 구현 내용

- `DatabaseConstraintError` 추가
- SQLite와 psycopg의 unique·foreign key·not-null 오류를 공통 `kind`로 변환
- SQLite adapter에서 `PRAGMA foreign_keys=ON` 활성화
- doctrine repository에 JSON metadata set/get helper 추가
- 테스트용 doctrine schema에 실제 외래키 관계 반영
- PostgreSQL 오류 후 savepoint rollback으로 후속 검증 가능하도록 구성

## 발견된 문제와 수정

1. PostgreSQL BOOLEAN 컬럼에 정수 리터럴을 사용하던 문제를 앞 단계에서 `TRUE/FALSE`로 수정했다.
2. SQLite 임시 schema에 외래키 선언이 빠져 있던 문제를 `REFERENCES`로 수정했다.
3. PostgreSQL constraint 오류 후 transaction이 aborted 되는 특성을 확인하고 savepoint을 적용했다.

## 테스트

- SQLite constraint contract: `2 passed`
- 실제 PostgreSQL constraint contract: `1 passed`
- 전체 회귀: `331 passed, 7 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

## 안전성

- 모든 PostgreSQL fixture는 transaction rollback으로 정리
- 운영 DB·운영 MinIO 변경 없음
- 기존 SQLite adapter 보존
- 비밀정보와 연결 문자열 미출력
- 운영 cutover 및 자동 migration 없음

## 남은 위험

- 전체 애플리케이션 repository가 아직 이 contract를 사용하도록 전환된 것은 아니다.
- UUID, timestamp 경계값, JSON schema 변화 및 deadlock/timeout은 추가 검증이 필요하다.
- PostgreSQL 운영 전환은 여전히 승인되지 않은 범위다.

## Rollback

- 새 contract는 명시적 테스트·adapter 경계에서만 사용된다.
- 기존 `DB_BACKEND=existing` 경로는 유지된다.
- PostgreSQL fixture는 rollback되어 테스트 데이터가 남지 않았다.

## 다음 권고

다음 단계는 **UUID·timestamp 경계값·JSON schema 변화·deadlock/timeout 회귀 시험**이다. 운영 DB와 운영 MinIO에는 적용하지 않는다.
