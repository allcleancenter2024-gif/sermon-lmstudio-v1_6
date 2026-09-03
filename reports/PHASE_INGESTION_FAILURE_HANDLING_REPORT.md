# Doctrine ingestion 장애·부분 성공 처리 보고서

## 판정

**조건부 완료**

테스트 전용 객체 업로드와 DB metadata 기록 사이의 부분 성공 상태를 명시적으로 처리하는 coordinator와 테스트를 추가했다. 기존 `snapshot_source` 실행 경로는 교체하지 않았으며, 운영 cutover도 수행하지 않았다.

## 변경 파일

- `app/ingestion_transaction.py`
- `tests/test_ingestion_transaction.py`
- `app/doctrine_storage.py`의 `StoredObject.version_id` 활용

## 상태 계약

| 상황 | 상태 | DB 기록 | orphan 후보 | 처리 |
|---|---|---:|---:|---|
| MinIO 업로드·DB 기록 성공 | `VERIFIED` | 있음 | 아니오 | 정상 완료 |
| MinIO 업로드 성공·DB 기록 실패 | `DB_FAILED` | 없음 | 예 | 자동 삭제 없이 감사 대상으로 전달 |
| MinIO 업로드 실패 | `STORAGE_FAILED` | 없음 | 아니오 | DB 기록 시도 없이 실패 보고 |

## 검증 결과

- 허용 prefix 검사: `_verification/` 밖의 key 차단
- 성공 경로: SHA-256 계산 후 업로드·metadata 기록
- DB 실패 경로: 객체 삭제 없이 orphan 후보 반환
- 저장소 실패 경로: DB insert 미호출 확인
- 기존 adapter·MinIO·orphan 관련 테스트: 통과

## 테스트

- 신규 장애 처리 테스트: `3 passed`
- 관련 테스트: `9 passed`
- 전체 회귀: `321 passed, 2 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

전체 회귀에서 Skip된 2건은 외부 PostgreSQL/MinIO 통합시험의 명시적 플래그가 없는 일반 실행을 안전하게 차단한 결과다. 실제 통합시험은 앞 단계에서 PostgreSQL CRUD `1 passed`, MinIO·PostgreSQL metadata 정합성 `1 passed`를 확인했다.

## 안전성

- 자동 object delete 없음
- 자동 DB delete 없음
- 운영 DB·운영 MinIO 미접근
- 테스트 prefix 외 쓰기 없음
- 오류 반환에 Secret·비밀번호·연결 문자열 없음
- 기존 SQLite ingestion 경로 보존

## 남은 위험

- 실제 `snapshot_source` 전체 경로에 coordinator를 연결하는 작업은 아직 별도 단계다.
- MinIO 성공 후 PostgreSQL 실패 시 실제 운영 복구 정책은 orphan 감사 결과를 기반으로 별도 승인해야 한다.
- 앱 재시작·timeout·강제 종료 중간 상태는 아직 추가 검증이 필요하다.

## Rollback

- 새 coordinator를 호출하지 않으면 기존 ingestion 경로가 유지된다.
- 새 파일과 테스트 파일을 제거해도 기존 SQLite DB와 MinIO adapter에는 영향이 없다.
- 테스트 객체는 자동 삭제하지 않으며, 별도 orphan 감사 후 명시적 승인으로만 정리한다.

## 다음 권고

다음 한 단계는 **timeout·강제 재시작·재시도 idempotency 검증**이다. 운영 환경이나 운영 객체에는 적용하지 않고, 테스트 DB와 `_verification/` prefix에서만 수행한다.
