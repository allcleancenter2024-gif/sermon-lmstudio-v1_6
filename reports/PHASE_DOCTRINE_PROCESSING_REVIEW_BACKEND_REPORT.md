# Phase 완료 보고

## 변경 목적

`doctrine_processing`의 문서 조회와 검토 상태 갱신을 저장소 팩토리 경계에 연결했다. 기본 실행 경로는 기존 SQLite를 유지하고, 명시적으로 선택된 PostgreSQL 백엔드는 동일한 저장소 계약을 사용하도록 정리했다.

## 변경 파일

- `app/doctrine_processing.py`
- `app/doctrine_repository_contract.py`
- `tests/test_doctrine_processing_review_backend.py`
- `reports/PHASE_DOCTRINE_PROCESSING_REVIEW_BACKEND_REPORT.md`

## 변경 내용

- 문서 처리 시작 시 `read_document_for_processing()`을 통해 문서 저장소에서 처리 필드를 조회한다.
- `write_document_review_state()`를 통해 검토 상태와 활성 상태를 갱신한다.
- 명시적 PostgreSQL 백엔드 사용 시 청크 저장, 검토 상태 갱신, 메타데이터 저장을 하나의 PostgreSQL 트랜잭션으로 묶었다.
- 기존 SQLite 호출부는 별도 백엔드 인자를 전달하지 않아도 동일하게 동작하도록 유지했다.
- SQLite 및 PostgreSQL 공통 저장소 계약에 문서 처리 조회와 검토 상태 갱신 메서드를 추가했다.
- SQLite 기본 계약의 문서 처리 헬퍼 회귀 테스트를 추가했다.

## 기존 기능 영향

- 기본 `process_doctrine_document(document_id, db_path, archive_root)` 호출 시 SQLite 동작을 유지한다.
- 운영 DB, 운영 MinIO 객체, Object Lock 및 Versioning 설정은 변경하지 않았다.
- LM Studio, 성경 근거 보호, 기존 RAG 및 UI 기능에는 변경을 가하지 않았다.

## 테스트

- 관련 테스트: `5 passed, 2 skipped`
- 전체 테스트: `339 passed, 10 skipped`
- 결과: 통과

통합 테스트의 `skipped`는 외부 PostgreSQL/MinIO 통합시험 플래그가 명시적으로 설정되지 않았기 때문이다. 단위·계약·기존 기능 회귀 검증은 완료했다.

## 발견된 문제

- 샌드박스 내부에서는 pytest 임시 디렉터리 생성 권한이 차단되어 외부 승인 실행으로 재시도했다. 코드 또는 테스트 실패는 아니었다.

## 남아 있는 위험

- 명시적 PostgreSQL 처리 백엔드의 실제 문서 처리 전체 흐름은 외부 통합시험 플래그 없이 실행하지 않았다.
- 실제 운영 전에는 테스트 DB와 테스트 버킷에서 PostgreSQL 문서 조회부터 청크 저장·메타데이터 기록까지 통합 검증이 필요하다.

## Rollback 방법

- 이번 Phase의 변경 파일 3개를 이전 버전으로 복원하면 된다.
- 삭제나 데이터 마이그레이션을 수행하지 않았으므로 DB 롤백 작업은 필요하지 않다.

## 다음 권장 단계

테스트 DB와 테스트 버킷을 대상으로 명시적 통합시험 플래그를 사용해 PostgreSQL 처리 백엔드의 전체 문서 처리 흐름을 1회 검증한다. 운영 환경 적용은 별도 승인 후 진행한다.
