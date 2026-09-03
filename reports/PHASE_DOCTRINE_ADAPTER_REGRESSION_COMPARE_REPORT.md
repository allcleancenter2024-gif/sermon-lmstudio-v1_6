# Doctrine SQLite/PostgreSQL adapter 회귀 비교 보고서

## 판정

**조건부 완료**

동일한 민감정보 없는 doctrine fixture를 SQLite와 PostgreSQL adapter에서 실행하고, 반환 결과와 transaction rollback 경계를 비교했다. 운영 DB와 운영 애플리케이션 경로는 변경하지 않았다.

## 비교 범위

- SQLite: 임시 database
- PostgreSQL: `sermon_db_restore_test_v2`
- fixture: 테스트 교단·출처·문서
- PostgreSQL 실행 방식: 하나의 transaction 후 의도적 rollback
- 운영 DB `sermon_db`: 미접근

## 결과

| 기능 | SQLite | PostgreSQL | 판정 |
|---|---|---|---|
| denomination 생성 | 성공 | 성공 | PASS |
| source 생성 | 성공 | 성공 | PASS |
| document 생성 | 성공 | 성공 | PASS |
| 반환 모델 정규화 | 동일 | 동일 | PASS |
| transaction rollback | 데이터 0건 | 데이터 rollback | PASS |
| Boolean 처리 | SQLite 호환 | PostgreSQL BOOLEAN 호환 | PASS |
| 운영 데이터 보호 | 변경 없음 | 운영 DB 미접근 | PASS |

## 발견 및 수정

초기 비교에서 PostgreSQL BOOLEAN 컬럼에 SQLite식 `1/0` 정수 리터럴을 사용해 datatype mismatch가 발생했다. 공통 SQL을 `TRUE/FALSE` 리터럴로 수정했고, 이후 양쪽 비교가 통과했다.

이 문제는 PostgreSQL adapter 전환 시 Boolean·SQL dialect 호환성 검토가 필요하다는 위험을 실제로 확인한 사례다.

## 테스트

- SQLite contract 비교: `1 passed`
- 실제 PostgreSQL 비교: `1 passed`
- 전체 회귀: `330 passed, 6 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

전체 회귀의 Skip 6건은 명시적 통합 플래그가 없을 때 외부 서비스 테스트를 자동 실행하지 않는 안전 게이트다.

## 안전성

- fixture는 transaction rollback으로 정리했다.
- 운영 DB·운영 MinIO 변경 없음
- 기존 SQLite adapter 보존
- PostgreSQL 전체 cutover 없음
- 민감정보 및 연결 문자열 출력 없음

## 남은 위험

- 현재 비교 contract는 doctrine 핵심 3개 테이블의 최소 CRUD 범위다.
- 전체 설교·RAG·설정·인증 repository는 아직 PostgreSQL 회귀 비교 대상이 아니다.
- timestamp, JSONB, UUID, unique/foreign key 오류 매핑은 기능별 추가 검증이 필요하다.

## Rollback

- 비교 adapter는 명시적 호출 경로에만 존재한다.
- 기존 SQLite 경로를 계속 사용하면 제품 동작은 기존 상태로 유지된다.
- 이번 PostgreSQL fixture는 rollback되어 데이터가 남지 않았다.

## 다음 권고

다음 단계는 **doctrine 기능군의 timestamp·JSONB·외래키·중복키 예외 계약 회귀 시험**이다. 운영 전환은 별도 승인 전까지 진행하지 않는다.
