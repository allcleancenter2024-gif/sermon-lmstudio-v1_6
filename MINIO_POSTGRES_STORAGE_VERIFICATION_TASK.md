# MinIO·PostgreSQL 안전 연결 및 저장소 검증 작업 지시서

## 1. 작업 목적

현재 프로그램에 다음 네 가지 설정을 안전하게 연결하고 검증한다.

1. MinIO 접속 주소
2. MinIO 최소 권한 서비스 계정
3. 테스트 버킷 및 테스트 prefix
4. PostgreSQL 테스트 데이터베이스

이번 작업의 목표는 운영 데이터를 변경하는 것이 아니라 다음 기능을 격리된 테스트 환경에서 확인하는 것이다.

- MinIO 연결 및 버킷 접근 권한
- 테스트 파일 업로드·다운로드
- SHA-256 checksum 검증
- 객체 Versioning 확인
- DB와 MinIO 객체 메타데이터 연결
- DB 레코드 복구 가능성 확인
- Object orphan 및 DB orphan 탐지

## 2. 안전 원칙

- 작업 시작 전에 현재 저장소 구조와 변경 상태를 확인한다.
- 기존 사용자 변경사항을 덮어쓰거나 삭제하지 않는다.
- 운영 DB와 운영 MinIO 객체를 변경하지 않는다.
- 관리자 Root 계정을 애플리케이션에 등록하지 않는다.
- 실제 비밀번호와 Secret Key를 소스, 로그, 테스트 결과 및 보고서에 출력하지 않는다.
- `.env` 실제 값은 Git에 커밋하지 않는다.
- 모든 쓰기 시험은 테스트 버킷의 `_verification/` prefix 안에서만 수행한다.
- Object Lock은 운영 버킷에 활성화하지 않는다.
- `COMPLIANCE` 잠금 모드는 사용하지 않는다.
- Object Lock 설정, 버킷 삭제, 객체 대량 삭제 및 DB 스키마 삭제는 사용자 승인 없이 수행하지 않는다.
- 설정값이 없으면 임의 값을 운영 설정으로 사용하지 않는다.
- 연결정보가 없으면 `.env.example`과 설정 가이드까지만 준비하고 실제 통합시험은 `BLOCKED`로 보고한다.
- 외부 네트워크 공개, 방화벽 변경 및 포트포워딩을 수행하지 않는다.

## 3. 1단계: 읽기 전용 사전 조사

다음 항목을 읽기 전용으로 조사한다.

- 현재 Git 상태와 프로젝트 루트
- `.env`, `.env.example` 존재 여부
- `docker-compose.yml` 또는 `compose.yml`
- MinIO 및 PostgreSQL/pgvector 서비스 정의
- 애플리케이션의 저장소 설정 모듈
- 데이터베이스 마이그레이션 도구
- MinIO SDK와 PostgreSQL 드라이버 의존성
- 기존 파일 업로드 코드와 객체 메타데이터 테이블
- 테스트 디렉터리와 테스트 실행 방법

권장 검색어:

```text
MINIO_
S3_
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
DATABASE_URL
POSTGRES_
bucket
object_key
version_id
checksum
sha256
pgvector
alembic
migration
```

프로그램 실행 위치를 판정하고 주소를 혼동하지 않는다.

| 실행 위치 | MinIO | PostgreSQL |
|---|---|---|
| Windows 호스트 | `http://127.0.0.1:9000` | `127.0.0.1:5432` |
| Docker Compose 내부 | `http://minio:9000` | `postgres:5432` |

조사 결과를 먼저 보고한 후 다음 단계로 진행한다.

## 4. 2단계: 환경변수 규격 정리

기존 설정 이름이 있다면 그것을 우선 사용하고 중복 변수 체계를 만들지 않는다. 필요한 경우 `.env.example`에 다음 항목을 추가한다.

```dotenv
# MinIO/S3-compatible object storage
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=replace_with_service_account
MINIO_SECRET_KEY=replace_with_secret
MINIO_BUCKET=sermon-documents-test
MINIO_TEST_PREFIX=_verification/
MINIO_REGION=us-east-1
MINIO_SECURE=false

# PostgreSQL test database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=sermon_db_test
POSTGRES_USER=sermon_user
POSTGRES_PASSWORD=replace_with_password
DATABASE_URL=postgresql://sermon_user:replace_with_password@postgres:5432/sermon_db_test
```

적용 조건:

- 기존 `.env` 실제 값은 변경하지 않는다.
- `.env.example`에는 실제 비밀번호를 기록하지 않는다.
- `.gitignore`에서 `.env`가 제외되고 `!.env.example`은 추적 가능한지 확인한다.
- Access Key는 필요한 경우 일부만 마스킹하고 Secret Key와 DB 비밀번호는 완전히 마스킹한다.
- 필수 설정 누락 시 이해하기 쉬운 오류를 반환하되 오류 메시지에 비밀정보를 포함하지 않는다.

## 5. 3단계: MinIO 연결 및 권한 점검

실제 설정값이 로컬 `.env`에 제공된 경우에만 수행한다.

### 5.1 읽기 전용 점검

- MinIO API 포트 연결 여부
- 서비스 계정 인증 성공 여부
- 대상 버킷 및 `_verification/` prefix 조회 가능 여부
- Versioning 상태 조회 가능 여부
- 서비스 계정의 실제 권한 범위

`mc admin info`는 관리자 권한이 필요할 수 있으므로 서비스 계정에서 실패하더라도 곧바로 연결 실패로 판정하지 않는다. 일반 버킷·객체 조회를 별도로 시험한다.

### 5.2 권한 경계 시험

| 시험 | 기대 결과 |
|---|---|
| 테스트 버킷 조회 | 성공 |
| `_verification/` 조회·업로드·다운로드 | 성공 |
| 운영 prefix 업로드 | `Access Denied` |
| 버킷 삭제·정책 변경·사용자 관리 | 권한 없음 |

운영 경로에 실제 객체를 쓰지 말고 권한 조회 또는 안전한 실패 확인 방식으로 시험한다.

## 6. 4단계: 업로드·checksum 검증

고유 실행 ID를 사용한다.

```text
_verification/{실행ID}/
```

시험 순서:

1. 임시 테스트 파일을 생성한다.
2. 업로드 전에 SHA-256을 계산한다.
3. 테스트 prefix에 업로드한다.
4. bucket, key, size, content type 및 version ID를 기록한다.
5. 객체를 새 임시 위치로 다운로드한다.
6. 다운로드 파일의 SHA-256을 계산한다.
7. 업로드 전후 SHA-256을 비교한다.
8. 결과를 `PASS`, `FAIL`, `SKIPPED`로 기록한다.

ETag를 SHA-256으로 간주하지 않는다. 검증 실패 객체는 운영 자료로 승격하지 않는다. 테스트 객체 정리는 별도 승인 또는 명시된 안전 조건에서만 수행한다.

## 7. 5단계: PostgreSQL 테스트 DB 확인

실제 테스트 DB 설정이 있을 때만 다음을 확인한다.

- DB 서버 및 `sermon_db_test` 연결
- 현재 사용자 권한
- pgvector 확장 사용 여부
- 기존 마이그레이션 상태
- 운영 DB와 테스트 DB 분리 여부

운영 DB로 판단되면 쓰기 시험을 중단하고 보고한다.

기존 스키마가 없다면 다음 필드를 포함하는 객체 메타데이터 구조를 제안한다.

```text
id
document_id
bucket_name
object_key
version_id
sha256
content_type
size_bytes
original_filename
upload_status
created_at
verified_at
```

기존 테이블이 있다면 새 테이블을 중복 생성하지 말고 기존 구조와의 매핑안을 제시한다. 마이그레이션 적용 전에는 대상이 테스트 DB인지 다시 확인한다.

## 8. 6단계: DB-객체 복구 테스트

테스트 데이터만 사용한다.

### 시나리오 A: 정상 등록

1. MinIO에 테스트 객체를 업로드한다.
2. checksum을 검증한다.
3. DB에 객체 메타데이터를 기록한다.
4. DB 값과 실제 객체 정보를 비교한다.

### 시나리오 B: DB 레코드 복구

1. 테스트 레코드를 백업한다.
2. 테스트 레코드만 제거하거나 복구 대상 상태로 표시한다.
3. MinIO 객체 메타데이터를 읽는다.
4. DB 레코드를 복원한다.
5. bucket, object key, version ID, 크기 및 SHA-256을 비교한다.

물리적 삭제보다 복구 상태 표시 또는 테스트 트랜잭션 롤백을 우선한다. 운영 레코드는 삭제하거나 수정하지 않는다.

## 9. 7단계: orphan 탐지

- **Object orphan:** MinIO 객체는 존재하지만 DB 레코드가 없음
- **DB orphan:** DB 레코드는 존재하지만 MinIO 객체가 없음

탐지 결과 필드:

```text
bucket
object_key
version_id
db_record_exists
object_exists
checksum_match
detected_at
recommended_action
```

초기 구현은 보고 전용으로 제한한다. orphan, DB 레코드, 운영 객체 또는 이전 버전을 자동 삭제·이동·정리하지 않는다.

## 10. 8단계: Versioning과 Object Lock

Versioning은 다음을 확인한다.

- 테스트 버킷 Versioning 활성화 여부
- 업로드 객체의 version ID
- 동일 key 재업로드 시 이전 버전 보존 여부

Object Lock은 기본적으로 상태 확인까지만 수행한다. 별도 잠금 테스트 버킷이 이미 있고 사용자 승인이 있을 때만 `GOVERNANCE` 모드를 시험한다.

다음은 수행하지 않는다.

- 운영 버킷 Object Lock 활성화
- `COMPLIANCE` 모드 또는 장기 retention 적용
- Legal Hold 설정
- 잠긴 객체 삭제 우회

## 11. 오류 및 중단 조건

다음 상황에서는 추측하거나 우회하지 말고 중단한다.

- MinIO Endpoint 또는 인증정보가 없음
- 대상 버킷이 운영용인지 테스트용인지 불명확함
- DB가 운영 DB인지 테스트 DB인지 불명확함
- `_verification/` 이외 경로에만 쓰기 권한이 있음
- 관리자 Root 계정만 제공됨
- TLS 인증서 오류가 발생함
- 기존 마이그레이션과 충돌함
- 기존 사용자 변경사항을 덮어써야 함
- Object Lock 변경 또는 복구 불가능한 변경이 필요함

TLS 검증을 임의로 끄거나 인증서 오류를 무시하지 않는다.

## 12. 테스트 항목

- 필수 환경변수 누락 테스트
- 비밀정보 로그 노출 방지 테스트
- MinIO 연결 성공·실패 테스트
- 허용 prefix 업로드 및 비허용 prefix 거부 테스트
- SHA-256 일치·불일치 테스트
- DB 메타데이터 저장 테스트
- Object orphan 및 DB orphan 탐지 테스트
- Versioning 정보 처리 테스트
- MinIO 또는 DB 장애 시 상태 처리 테스트

실제 외부 서비스가 없으면 단위 테스트 또는 모의 S3 테스트로 대체하고 실제 통합시험 미실행 사실을 명시한다.

## 13. 완료 기준

- [ ] 기존 구조와 설정 방식을 조사했다.
- [ ] `.env.example`에 비밀값 없는 설정 예시가 있다.
- [ ] `.env`가 Git에서 제외되어 있다.
- [ ] 관리자 계정과 서비스 계정이 분리되어 있다.
- [ ] 서비스 계정 권한이 테스트 prefix로 제한되어 있다.
- [ ] MinIO 연결과 테스트 버킷을 확인했다.
- [ ] 테스트 업로드·다운로드 및 SHA-256 검증이 성공했다.
- [ ] PostgreSQL 테스트 DB 연결을 확인했다.
- [ ] DB와 MinIO 메타데이터 연결·복구를 검증했다.
- [ ] 두 종류의 orphan을 탐지할 수 있다.
- [ ] Versioning 상태를 확인했다.
- [ ] Object Lock을 승인 없이 변경하지 않았다.
- [ ] 운영 데이터가 변경되지 않았다.
- [ ] 관련 테스트가 통과했다.

설정 부재로 실행하지 못한 항목은 `BLOCKED` 또는 `SKIPPED`로 구분하고 필요한 설정을 정확히 보고한다.

## 14. 최종 보고서 형식

### A. 작업 결과 요약

```text
전체 판정:
변경 파일:
통과 항목:
실패 항목:
보류 항목:
운영 데이터 변경 여부:
```

### B. 연결 및 권한 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| MinIO 연결 | PASS/FAIL/BLOCKED | |
| 테스트 버킷 조회 | PASS/FAIL/BLOCKED | |
| prefix 쓰기 | PASS/FAIL/BLOCKED | |
| 운영 경로 차단 | PASS/FAIL/BLOCKED | |
| PostgreSQL 연결 | PASS/FAIL/BLOCKED | |

### C. 데이터 무결성 결과

| 항목 | 결과 | 세부 내용 |
|---|---|---|
| 업로드 | | |
| 다운로드 | | |
| SHA-256 | | |
| Versioning | | |
| DB 메타데이터 | | |
| 복구 시험 | | |
| orphan 탐지 | | |

### D. 보안 점검

- 실제 비밀정보 노출 여부
- Root 계정 사용 여부
- 최소 권한 적용 여부
- 운영 데이터 변경 여부
- Object Lock 변경 여부

### E. 다음 단계 권고

다음 단계는 한 번에 하나만 제안한다. 운영 적용은 자동 진행하지 말고 사용자 승인을 기다린다.

## 15. 실행 지시

지금은 먼저 1단계의 읽기 전용 사전 조사를 수행한다. 조사 후 다음을 보고한다.

1. 현재 MinIO·PostgreSQL 구성 상태
2. 이미 존재하는 환경변수 이름
3. 누락된 설정
4. 수정이 필요한 파일 후보
5. 운영 데이터에 영향을 주지 않는 실행 계획
6. 실제 통합시험 가능 여부

치명적인 충돌이 없으면 안전한 설정 파일 보완과 테스트 구현까지 진행한다. 실제 접속정보가 없으면 Secret Key나 비밀번호를 대화창에 입력하도록 요구하지 말고, 사용자가 로컬 `.env`에 직접 입력할 변수 이름과 위치만 안내한다.
