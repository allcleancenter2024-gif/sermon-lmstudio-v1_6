# Doctrine Adapter·MinIO·PostgreSQL 정합성 단계 보고서

## 판정

**조건부 완료**

테스트 전용 교리 객체 저장 경로에 한해 SQLite/PostgreSQL repository contract와 MinIO metadata 연결을 검증했다. 운영 DB cutover와 전체 애플리케이션 adapter 전환은 수행하지 않았다.

## 변경 내용

- `StoredObject`에 `version_id`를 추가했다.
- MinIO 업로드 후 `stat_object`로 Versioning 정보를 읽는다.
- Versioning이 꺼진 버킷에서는 `version_id=None`을 정상 처리한다.
- 최소 권한 계정에서 허용되지 않는 버킷 루트 `bucket_exists()` 사전 조회를 제거했다.
- 지정된 객체 경로에서 업로드·조회 권한 오류를 판정하도록 변경했다.
- 실제 통합시험을 추가했다.

## 실제 통합시험

| 항목 | 결과 | 근거 |
|---|---|---|
| PostgreSQL adapter CRUD/rollback | PASS | `sermon_db_test`에서 실제 실행 |
| MinIO 업로드 | PASS | `sermon-documents-test/_verification/` 아래 실행 |
| SHA-256 | PASS | 업로드 전후 digest 및 DB 저장값 비교 |
| object key | PASS | MinIO key와 DB `object_key` 비교 |
| version ID | PASS | MinIO 반환값과 DB `version_id` 비교; 현재 unversioned라 NULL |
| 객체 크기 | PASS | MinIO 저장 크기와 DB `size_bytes` 비교 |
| 운영 경로 접근 | 미수행 | 운영 객체 쓰기를 금지하는 범위 준수 |

## 테스트 결과

- 관련 테스트: `6 passed, 1 skipped`
- 실제 MinIO·PostgreSQL 통합시험: `1 passed`
- 전체 회귀: `318 passed, 2 skipped`
- 의존성: `No broken requirements found`
- compileall: PASS

전체 회귀의 Skip 2건은 실제 외부 서비스 통합시험을 명시적 플래그 없이 자동 실행하지 않는 안전 게이트이다. 통합시험 자체는 별도 실행으로 통과했다.

## 발견 및 수정한 문제

최소 권한 테스트 계정은 객체 prefix 접근은 허용하지만 버킷 루트 `HEAD` 조회는 허용하지 않았다. 기존 adapter가 `bucket_exists()`를 먼저 호출해 `AccessDenied`가 발생했다. 이 불필요한 권한 의존성을 제거했으며, 운영 경로에 대한 우회나 권한 확대는 하지 않았다.

## 데이터 보호

- 테스트 객체는 `sermon-documents-test/_verification/` 아래에만 생성했다.
- 테스트 DB는 `sermon_db_test`만 사용했다.
- 운영 DB `sermon_db`와 SQLite 원본은 변경하지 않았다.
- 테스트 객체와 대응 DB metadata는 검증 후 추적 가능하도록 유지했다.
- 자동 삭제·운영 승격·Object Lock 변경은 수행하지 않았다.

## 남은 위험

- 전체 애플리케이션은 여전히 SQLite 직접 접근 구조다.
- 현재 테스트 버킷은 Versioning이 꺼져 있어 실제 이전 version 보존 동작은 검증하지 않았다.
- DB 장애·MinIO 성공 후 DB 실패의 보상 처리와 애플리케이션 재시작 복구는 다음 별도 단계다.

## Rollback

- `DB_BACKEND=existing` 또는 미설정으로 기존 SQLite 경로를 유지한다.
- 새 adapter 및 통합 테스트 파일은 기존 SQLite DB를 변경하지 않는다.
- 테스트 객체·레코드는 테스트 prefix와 테스트 DB에 한정된다.

## 다음 권고

다음 한 단계는 **DB 장애·MinIO 장애를 포함한 doctrine ingestion transaction 상태 처리**를 테스트 DB와 테스트 prefix에서 검증하는 것이다. 운영 전환은 별도 승인 전까지 진행하지 않는다.
