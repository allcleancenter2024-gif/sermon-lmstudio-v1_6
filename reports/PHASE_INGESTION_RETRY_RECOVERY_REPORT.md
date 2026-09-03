# Doctrine ingestion timeout·재시작·재시도 보고서

## 판정

**조건부 완료**

테스트 전용 ingestion coordinator에 timeout 실패 상태, 새 adapter 인스턴스 재연결, 동일 객체 재시도의 idempotency를 추가 검증했다. 운영 ingestion 경로와 운영 데이터는 변경하지 않았다.

## 검증 결과

| 항목 | 결과 | 세부 내용 |
|---|---|---|
| Timeout | PASS | `TimeoutError`가 `STORAGE_FAILED`로 변환되고 DB insert를 시도하지 않음 |
| 강제 종료에 준하는 재연결 | PASS | 기존 transaction 종료 후 새 adapter 인스턴스에서 `VERIFIED` 레코드 재조회 |
| 동일 key 재시도 | PASS | 동일 checksum·크기이면 `RETRY_REUSED`, 중복 레코드 0건 추가 |
| 객체 metadata 충돌 | PASS | 다른 checksum·크기이면 `DB_CONFLICT` 및 orphan 후보 보고 |
| 저장소 장애 | PASS | `STORAGE_FAILED`, DB 미기록 |
| DB 장애 | PASS | `DB_FAILED`, 객체 자동 삭제 없음 |
| 자동 정리 | PASS | object/DB 자동 삭제 미수행 |

## 변경 파일

- `app/db_adapter.py`
  - NULL-safe `find_by_object` 추가
- `app/ingestion_transaction.py`
  - `RETRY_REUSED` 및 `DB_CONFLICT` 상태 추가
  - 재시도 시 기존 metadata 확인
- `tests/test_ingestion_transaction.py`
  - idempotency, timeout, 새 adapter 재연결 테스트 추가

## 테스트

- 관련 테스트: `8 passed`
- 전체 회귀: `324 passed, 2 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

전체 회귀에서 Skip된 2건은 실제 PostgreSQL/MinIO 통합시험의 명시적 환경변수 게이트다. 운영 서비스에 자동 연결하지 않도록 의도된 동작이다.

## 안전성

- 대상 prefix는 `_verification/`으로 제한
- 테스트 DB만 사용
- 운영 DB·운영 MinIO 변경 없음
- timeout 및 DB 오류 메시지에 Secret·비밀번호·연결 문자열 없음
- orphan은 보고 후보로만 남기고 자동 삭제하지 않음
- 기존 SQLite adapter와 ingestion 경로 보존

## 남은 위험

- 실제 프로세스 강제 종료 중 업로드와 DB 기록의 원자성은 구조적으로 보장할 수 없으며, 재시작 후 orphan audit가 필요하다.
- 현재 Versioning 비활성 버킷에서는 version ID 재시도 분리가 제한된다.
- 실제 `snapshot_source` 전체 경로에 coordinator를 연결하는 작업은 아직 별도 승인 범위다.

## Rollback

- 새 coordinator를 호출하지 않으면 기존 SQLite ingestion 경로를 사용한다.
- adapter 파일과 테스트 파일을 되돌려도 기존 DB·MinIO 객체는 삭제되지 않는다.

## 다음 권고

다음 단계는 **테스트 DB 백업·복원 및 PostgreSQL schema restore 절차 검증**이다. 운영 DB에는 적용하지 않고, 테스트 DB 백업 파일과 복구 가능한 별도 테스트 대상에서만 수행한다.
