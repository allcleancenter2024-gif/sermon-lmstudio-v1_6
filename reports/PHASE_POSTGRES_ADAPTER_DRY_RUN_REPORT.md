# PostgreSQL Adapter Migration Dry-run 보고서

## A. 최종 판정

**조건부 완료**

이번 단계는 기존 SQLite 애플리케이션을 PostgreSQL로 전환하지 않고, 테스트 DB에서만 명시적 adapter 경계와 객체 메타데이터 CRUD·transaction rollback을 검증하는 범위로 완료했다.

## B. 변경 요약

- 추가: `app/db_adapter.py`
- 추가: `tests/test_db_adapter.py`
- 추가: `tests/test_postgres_adapter_integration.py`
- 수정: `requirements.txt` (`psycopg[binary]` 추가)
- 수정: `pytest.ini` (`integration` marker 등록)
- 추가: 본 보고서
- 기존 `app/core.py`, 기존 SQLite repository 및 운영 설정은 변경하지 않았다.
- 운영 DB, 운영 MinIO 객체 및 운영 환경변수는 변경하지 않았다.
- 테스트 DB에는 기존 단계에서 생성된 테스트 스키마만 사용했고, 통합시험 임시 레코드는 시험 후 정리했다.

## C. 조사 결과

- 현재 제품 DB 실행 경로는 `data/bible.db` SQLite이다.
- `app/core.py`, `auth.py`, `backup.py`, doctrine 처리 모듈 및 일부 route는 SQLite에 직접 접근한다.
- 기존 repository는 SQLite 전용이며, 전체 애플리케이션 adapter 교체는 별도 Phase가 필요하다.
- ORM, SQLAlchemy, Alembic, psycopg 기반의 기존 adapter/session factory는 없었다.
- `DB_BACKEND`는 새 factory에서만 사용하며 기본값은 `existing`이다.
- `DB_BACKEND=postgres`는 `DATABASE_URL`이 없거나 잘못된 경우 조용히 SQLite로 fallback하지 않는다.

## D. Adapter 비교

| 기능 | 기존 adapter | PostgreSQL adapter | 판정 |
|---|---|---|---|
| 연결 | SQLite 파일 연결 | psycopg 연결 | PASS (각 경로 별도 확인) |
| CRUD | 객체 메타데이터 repository 계약 | 동일 repository 계약 | PASS |
| transaction | context manager commit/rollback | psycopg context manager commit/rollback | PASS |
| MinIO 연계 | 기존 Local/MinIO 저장 경계 보존 | 객체 레코드 참조 스키마 대상 | 조건부 |
| 재시작 복구 | 기존 앱 경로 보존 | 연결 재생성 구조만 확인 | SKIPPED |

## E. 마이그레이션 및 정합성 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| 스키마 생성 | PASS | `sermon_db_test`에 교리·객체 메타데이터 스키마 존재 |
| 테스트 데이터 이전 | PASS | 익명화된 교단 1건·출처 1건 확인; 운영 전체 복사 없음 |
| 행 수·관계 검증 | PASS | `denominations=1`, `doctrine_sources=1`, 외래키 고아 0건 |
| 객체 메타데이터 CRUD | PASS | 실제 `sermon_db_test`에서 생성·조회 후 정리 |
| checksum/version 참조 | SKIPPED | 현재 PostgreSQL 객체 레코드가 비어 있고 Versioning은 별도 미검증 |
| transaction rollback | PASS | 임시 레코드 상태 변경을 rollback 후 원상태 확인 |
| schema downgrade | SKIPPED | 삭제형 downgrade는 승인 없이 실행하지 않음; restore 절차를 운영 전환 전에 별도 작성해야 함 |
| 기존 SQLite 보존 | PASS | `data/bible.db`를 읽기 전용 확인; 기존 adapter·스키마 유지 |

## F. 테스트

- 기준선: `316 passed`
- adapter 단위/안전 게이트: `2 passed, 1 skipped`
- 실제 PostgreSQL 통합시험: `1 passed`
- 전체 회귀: `318 passed, 1 skipped`
- 의존성 검사: `No broken requirements found`
- skip 사유: 통합시험은 명시적 `RUN_POSTGRES_INTEGRATION=1` 없이는 실행하지 않도록 안전 게이트를 둠

## G. 보안 및 중단 조건 점검

- Secret/비밀번호/연결 문자열: 코드·로그·보고서에 출력하지 않음
- Root 계정: 애플리케이션 adapter에 사용하지 않음
- 최소 권한 MinIO 계정: 기존 test/production 계정과 prefix 정책 유지
- 운영 DB: 변경 없음. `sermon_db`에는 이번 대상 테이블이 없음
- 운영 MinIO: 변경 없음
- Object Lock/Legal Hold/운영 Versioning: 변경 없음
- 자동 cutover, 자동 rollback, orphan 자동 삭제: 수행하지 않음

## H. 남아 있는 위험

1. **높음 — 전체 애플리케이션은 아직 SQLite 직접 접근 구조다.**
   - 영향: 현재 adapter는 드라이런 대상 범위에 한정되며 전체 제품의 PostgreSQL 호환성을 보장하지 않는다.
   - 권고: 다음 Phase에서 repository contract를 먼저 정하고, 기능군별로 작은 단위 회귀 테스트를 추가한다.
2. **중간 — PostgreSQL schema downgrade가 실행 검증되지 않았다.**
   - 영향: 운영 전환 전 복원 시간이 보장되지 않는다.
   - 권고: 테스트 DB 백업/복원 절차를 문서화하고 별도 승인 후 재현한다.
3. **중간 — MinIO Versioning과 실제 object key/checksum의 PostgreSQL 참조 통합시험이 남아 있다.**
   - 영향: version_id 및 객체-DB 정합성의 전체 경로가 아직 조건부다.
   - 권고: Versioning이 활성화된 별도 테스트 버킷에서만 수행한다.

## I. Rollback 방법

- 애플리케이션은 `DB_BACKEND=existing` 또는 해당 변수 미설정 상태에서 기존 SQLite 경로를 사용한다.
- 새 adapter 파일과 테스트는 기존 SQLite 파일/테이블을 변경하지 않으므로 파일 단위 revert로 제거할 수 있다.
- PostgreSQL 테스트 레코드는 통합시험에서 정리되었고, 테스트 스키마 삭제는 수행하지 않았다.
- 운영 전환 전에는 PostgreSQL 백업 복원과 schema rollback 문서를 별도 승인·검증해야 한다.

## J. 다음 단계 권고

**adapter 보완**을 권고한다. 전체 cutover는 승인하지 않는다. 다음 한 단계는 `doctrine` 기능군의 repository contract를 PostgreSQL/SQLite 양쪽에 연결하고, MinIO object key·version_id·SHA-256과 DB 레코드의 실제 통합시험을 테스트 DB에서만 수행하는 것이다.
