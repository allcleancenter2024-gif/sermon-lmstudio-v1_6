# 테스트 환경 운영 전환 readiness audit 보고서

## 판정

**조건부 완료 — 테스트 환경 readiness PASS**

운영 전환을 실행하지 않고, 복원된 테스트 DB와 테스트 MinIO를 대상으로 전환 전제조건을 자동 산출했다.

## 점검 항목

| 항목 | 결과 | 근거 |
|---|---|---|
| DB가 테스트 DB인지 | PASS | `sermon_db_restore_test_v2` 확인 |
| Schema manifest 일치 | PASS | 필수 테이블·확장·version 일치 |
| `vector` 확장 | PASS | DB에서 확인 |
| MinIO endpoint | PASS | localhost endpoint |
| MinIO bucket | PASS | `sermon-documents-test` |
| 테스트 prefix | PASS | `_verification/` |
| 자격증명 존재 여부 | PASS | 값은 출력하지 않고 존재만 확인 |
| MinIO read probe | PASS | `_verification/` 목록 조회 |
| 운영 DB 접근 | PASS | 접근하지 않음 |

## 발견된 문제와 수정

복원 DB 이름 `sermon_db_restore_test_v2`가 안전한 테스트 DB임에도 기존 판정식이 이름이 정확히 `_test`로 끝나는 경우만 허용했다. `*_test_*` 패턴도 테스트 DB로 인정하도록 수정했으며, 운영 이름 `sermon_db`는 계속 거부한다.

## 테스트

- readiness 단위 테스트: `4 passed`
- 실제 복원 DB·MinIO readiness audit: `1 passed`
- 전체 회귀: `329 passed, 5 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

## 안전성

- readiness audit는 DB 및 MinIO에 read-only 작업만 수행했다.
- 테스트 객체 업로드·삭제 없음
- 운영 DB·운영 MinIO 미접근
- Secret과 비밀번호 미출력
- PASS는 테스트 환경에만 적용되며 운영 전환 승인을 의미하지 않음

## 남은 위험

- 애플리케이션 전체는 아직 SQLite 기반이며 PostgreSQL 운영 cutover는 검증되지 않았다.
- 운영 전환에는 별도 운영 backup 보존, PITR, 복원 시간, 모니터링 및 rollback 계획이 필요하다.
- Versioning/Object Lock 운영 정책은 이번 범위에 포함하지 않았다.

## Rollback

- readiness audit 코드 실행을 중단해도 DB·MinIO 상태에는 영향이 없다.
- 이번 단계의 code change는 테스트-only checklist이며 기존 SQLite 경로를 변경하지 않는다.

## 다음 권고

다음 단계는 **운영 전환이 아닌 PostgreSQL adapter의 doctrine 기능군 회귀 비교**다. SQLite와 PostgreSQL에서 동일한 테스트 fixture를 실행해 결과·예외·transaction 경계를 비교해야 한다.
