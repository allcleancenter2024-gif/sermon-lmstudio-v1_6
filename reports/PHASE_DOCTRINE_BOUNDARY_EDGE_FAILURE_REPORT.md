# Doctrine adapter 경계값·일시 장애 회귀 보고서

## 판정

**조건부 완료**

UUID, timestamp timezone, JSON schema 확장, PostgreSQL timeout 및 deadlock 계열 오류 분류를 테스트 환경에서 검증했다. 운영 DB·운영 MinIO에는 접근하지 않았다.

## 결과

| 항목 | 결과 | 세부 내용 |
|---|---|---|
| UUID metadata record | PASS | UUID key 저장·재조회 |
| timestamp 경계 | PASS | epoch 경계 값 및 PostgreSQL timezone-aware datetime 확인 |
| JSON schema 확장 | PASS | nested/list/schema_version 필드 round-trip |
| unique 오류 | PASS | 공통 `DatabaseConstraintError(kind='unique')` |
| foreign key 오류 | PASS | 공통 `DatabaseConstraintError(kind='foreign_key')` |
| deadlock 분류 | PASS | retryable `DatabaseTransientError(kind='deadlock')` |
| lock timeout 분류 | PASS | retryable `DatabaseTransientError(kind='lock_timeout')` |
| query timeout | PASS | 실제 PostgreSQL statement timeout에서 `query_timeout` 확인 |
| 운영 데이터 | PASS | 운영 DB·MinIO 미접근 |

## 구현 내용

- `DatabaseTransientError` 추가
- deadlock, lock timeout, query timeout을 retryable 종류로 매핑
- PostgreSQL/SQLite 공통 doctrine metadata contract 확장
- 테스트 DB에서 오류 발생 시 savepoint 또는 전체 rollback 사용

## 테스트

- 경계값·오류 단위 테스트: `2 passed`
- 실제 PostgreSQL timeout 통합시험: `1 passed`
- 전체 회귀: `333 passed, 8 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

전체 회귀의 Skip 8건은 외부 통합시험을 명시적 환경변수 없이 자동 실행하지 않는 안전 게이트다.

## 안전성

- fixture는 transaction rollback으로 정리
- 운영 DB·운영 MinIO 변경 없음
- 운영 cutover 없음
- 오류 출력에 Secret·비밀번호·연결 문자열 없음
- timeout 시험은 200ms 제한으로 실행

## 남은 위험

- 실제 다중 worker deadlock 재현은 환경 영향 때문에 짧은 오류 분류 테스트로 제한했다.
- retry 정책 자체(지수 backoff, 최대 횟수, 중복 방지)는 아직 애플리케이션 ingestion 경로에 연결하지 않았다.
- 전체 애플리케이션 PostgreSQL 전환은 수행하지 않았다.

## Rollback

- 새 오류 contract는 명시적 adapter/repository 경계에서만 사용된다.
- 기존 SQLite 경로는 유지된다.
- PostgreSQL fixture는 rollback되어 데이터가 남지 않았다.

## 다음 권고

다음 단계는 **doctrine adapter의 테스트 결과를 하나의 phase readiness 보고서로 통합하고 운영 전환 차단 조건을 자동 확인하는 것**이다. 운영 cutover는 별도 승인 전까지 진행하지 않는다.
