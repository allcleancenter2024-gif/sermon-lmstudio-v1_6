# 다음 단계 작업 지시서

## PostgreSQL 운영 전환 준비 및 애플리케이션 DB Adapter 마이그레이션 드라이런

## 1. 이전 단계 판정

이전 단계는 조건부 완료이다. MinIO·PostgreSQL 테스트 환경, 최소 권한 정책, 테스트 버킷, SHA-256, DB 객체 메타데이터, rollback, orphan 판정 및 비밀정보 보호는 완료되었다.

아직 운영 DB 전환, 운영 버킷 Versioning, Object Lock, 운영 객체 감사 및 애플리케이션 전체 DB adapter 전환은 보류 상태다.

## 2. 다음 작업 선정

다음 작업은 실제 애플리케이션의 DB 접근 구조를 조사하고 PostgreSQL adapter 전환을 테스트 환경에서 드라이런하는 것이다.

운영 DB 전환과 운영 스토리지 변경은 이번 범위에서 제외한다. DB adapter와 마이그레이션·롤백 경로가 먼저 검증되어야 이후 운영 전환을 안전하게 판단할 수 있다.

## 3. 작업 목표

1. 애플리케이션 전체 DB 접근 지점을 파악한다.
2. 기존 DB 구현과 비즈니스 로직의 결합도를 확인한다.
3. 기존 기능을 보존하면서 PostgreSQL adapter를 선택할 수 있는 구조를 만든다.
4. 테스트 DB에서 스키마 생성·데이터 이전·정합성 검사를 드라이런한다.
5. 기존 DB로 되돌릴 수 있는 롤백 경로를 검증한다.
6. 운영 전환에 필요한 조건과 위험을 보고한다.

## 4. 안전 원칙

- 운영 DB, 운영 데이터 및 운영 환경변수를 변경하지 않는다.
- 기존 DB 파일, 테이블, 마이그레이션 또는 사용자 데이터를 삭제하지 않는다.
- 기존 adapter를 제거하지 않는다.
- 실제 비밀번호, 연결 문자열 및 Secret을 로그나 보고서에 출력하지 않는다.
- 테스트는 별도 PostgreSQL 테스트 DB와 테스트 데이터로 수행한다.
- destructive migration, 자동 cutover, 자동 rollback 및 운영 배포를 수행하지 않는다.
- 기존 사용자 변경사항과 충돌하면 중단하고 보고한다.
- 테스트하지 않은 내용을 완료로 표시하지 않는다.

## 5. 1단계: 읽기 전용 구조 조사

소스 변경 없이 다음을 조사한다.

- 현재 DB 종류와 기본 실행 경로
- SQLite, PostgreSQL 또는 기타 DB 사용 여부
- ORM, SQL 라이브러리, 연결 풀 및 session 생성 위치
- Repository·Service·Route 계층
- 마이그레이션 도구 및 앱 시작 시 자동 스키마 변경 여부
- 동기·비동기 접근 혼용 여부
- 테스트 fixture와 백그라운드 작업의 DB 접근
- MinIO 업로드·객체 메타데이터 관련 DB 접근

권장 검색어:

~~~text
DATABASE_URL
sqlite
postgresql
create_engine
sessionmaker
AsyncSession
execute
commit
rollback
repository
migration
alembic
metadata.create_all
~~~

Repository를 우회하여 Route, UI handler, Service, worker, CLI, 테스트 및 시작 이벤트에서 DB에 직접 접근하는지 확인한다.

| 파일 | 함수/클래스 | 현재 DB 접근 | Repository 경유 | PostgreSQL 위험 |
|---|---|---|---|---|
| | | | | |

SQLite 전용 SQL, 예약어, Boolean·DateTime·JSON·UUID, 자동 증가 키, 외래키, UPSERT, NULL, transaction, pgvector 및 unique 조건의 호환성을 조사한다.

변경 전에 현재 구조, 영향 범위, 직접 접근 목록, 호환성 위험, 수정 후보 파일, 테스트 및 롤백 전략을 보고한다.

## 6. 2단계: DB Adapter 경계 설계

기존 프로젝트 패턴을 우선하며 과도한 추상화나 새 프레임워크를 도입하지 않는다.

~~~text
Application 또는 Service
        ↓
Repository contract
        ↓
기존 DB adapter | PostgreSQL adapter
~~~

설계 원칙:

- 비즈니스 로직은 DB 종류를 직접 알지 못한다.
- DB 선택은 환경설정과 명시적 factory에서만 수행한다.
- Repository 반환 모델, 예외 계약 및 transaction 경계를 유지한다.
- 기존 adapter는 롤백 수단으로 보존한다.
- 잘못된 backend 값은 조용히 fallback하지 말고 안전하게 실패한다.

환경변수 예시:

~~~dotenv
DB_BACKEND=existing
DATABASE_URL=replace_with_test_database_url
~~~

실제 변수명은 기존 설정 체계가 있으면 그것을 우선 사용한다.

## 7. 3단계: PostgreSQL 호환 구현

조사 결과 필요한 최소 범위만 수정한다.

- PostgreSQL 연결과 session lifecycle
- Repository CRUD와 transaction commit·rollback
- UUID, JSON, timestamp 및 Boolean 처리
- MinIO 객체 메타데이터와 업로드 상태 저장
- timeout, duplicate key, 외래키 오류의 예외 매핑
- 앱 종료 시 연결 풀 정리

Route나 UI에서 SQL을 직접 실행하지 않는다. adapter별 비즈니스 규칙을 복제하지 않는다. DB 장애 시 임시 DB로 자동 전환하거나 앱 시작 시 운영 스키마를 자동 변경하지 않는다.

## 8. 4단계: 마이그레이션 드라이런

별도 PostgreSQL 테스트 DB에서만 다음 순서로 수행한다.

1. 대상이 테스트 DB인지 확인하고 백업 또는 재생성 가능성을 확인한다.
2. 마이그레이션 버전과 대상 스키마 상태를 확인한다.
3. 테스트 DB에 스키마를 생성한다.
4. 최소 fixture 또는 익명화된 표본 데이터를 준비한다.
5. PostgreSQL 테스트 DB로 이전한다.
6. 행 수, 기본키, 외래키 및 주요 필드를 비교한다.
7. MinIO object key·version ID·SHA-256 참조를 비교한다.
8. 주요 애플리케이션 기능을 실행한다.
9. downgrade 또는 별도 복원 절차를 시험한다.
10. 결과와 소요 시간을 기록한다.

운영 데이터 전체를 복사하지 않는다. 개인정보, Secret 및 민감한 본문은 제거하거나 익명화한다.

## 9. 데이터 정합성 검증

| 검사항목 | 성공 조건 |
|---|---|
| 테이블·행 수 | 예상값과 일치 |
| 기본키 | 누락·중복 없음 |
| 외래키 | 고아 참조 없음 |
| 필수 컬럼 | 예상 밖 NULL 없음 |
| timestamp | timezone 의미 보존 |
| JSON | 파싱과 의미 동일 |
| MinIO key | 테스트 객체와 연결 |
| version ID | 존재 시 동일 |
| SHA-256 | 저장값과 객체 checksum 일치 |

결과는 PASS, FAIL, BLOCKED, SKIPPED로 구분한다.

## 10. 기능 회귀 테스트

동일한 시나리오를 기존 adapter와 PostgreSQL adapter에 실행한다.

- 로그인 또는 사용자 조회
- 설정 저장·불러오기
- 문서·설교 생성 레코드 저장
- 목록·상세·수정 조회
- MinIO 업로드와 메타데이터 저장
- 업로드 실패 시 DB rollback
- DB 실패 시 객체 상태 처리
- orphan 판정
- 애플리케이션 재시작 후 재조회

## 11. 장애 및 롤백 시험

잘못된 DB 비밀번호, PostgreSQL 중단, timeout, transaction 중간 실패, duplicate key, MinIO 성공 후 DB 실패, DB 기록 전 MinIO 실패 및 앱 강제 재시작을 시험한다.

롤백 검증 목표:

1. 기존 adapter로 되돌릴 수 있다.
2. 기존 DB와 데이터가 유지된다.
3. PostgreSQL 장애가 기존 DB를 손상시키지 않는다.
4. 부분 성공 레코드를 탐지할 수 있다.
5. orphan을 자동 삭제하지 않고 보고한다.

## 12. 필수 테스트

- adapter contract 및 Repository CRUD
- transaction rollback
- PostgreSQL 통합 테스트
- 기존 adapter 회귀 테스트
- migration upgrade와 지원 가능한 downgrade 또는 restore
- MinIO·DB 일관성
- 환경변수 누락과 잘못된 backend 값
- Secret 마스킹

실제 PostgreSQL 통합시험을 실행하지 못하면 모의 테스트 통과만으로 완료 판정하지 않는다.

## 13. 완료 기준

- [ ] 모든 DB 접근 지점과 Repository 우회가 조사되었다.
- [ ] 기존 DB와 PostgreSQL 호환성 위험이 정리되었다.
- [ ] adapter 선택 경계가 명확하고 기존 adapter가 보존되었다.
- [ ] PostgreSQL 테스트 DB에서 CRUD와 rollback이 동작한다.
- [ ] 마이그레이션 드라이런과 정합성 검사가 완료되었다.
- [ ] MinIO 객체 메타데이터 참조가 검증되었다.
- [ ] 두 adapter의 회귀 결과가 비교되었다.
- [ ] 롤백 경로가 검증되었다.
- [ ] Secret이 코드·로그·보고서에 노출되지 않았다.
- [ ] 운영 DB와 운영 객체가 변경되지 않았다.

## 14. 중단 조건

- 테스트 DB와 운영 DB를 구분할 수 없음
- 기존 DB 스키마가 문서·코드와 불일치
- 데이터 손실 가능성이 있는 migration 필요
- downgrade 또는 복원 방법이 없음
- 기존 adapter 제거가 필요함
- 운영 환경변수 변경이 필요함
- 실제 사용자 데이터가 필요함
- 사용자 변경사항과 충돌함
- 범위 밖 구조 개편이 필요함

## 15. 제외 범위

- 운영 DB PostgreSQL cutover와 전체 데이터 이전
- 운영 DATABASE_URL 변경과 기존 DB 폐기
- 운영 MinIO 버킷 변경 및 Versioning 활성화
- Object Lock·Legal Hold 적용
- 운영 객체 전체 감사
- 프로덕션 배포

## 16. 최종 보고서 형식

### A. 최종 판정

PASS / 조건부 완료 / FAIL / BLOCKED

### B. 변경 요약

- 변경 파일, migration, 테스트 및 환경변수
- 운영 데이터 변경 여부

### C. Adapter 비교

| 기능 | 기존 adapter | PostgreSQL adapter | 판정 |
|---|---|---|---|
| 연결 | | | |
| CRUD | | | |
| transaction | | | |
| MinIO 연계 | | | |
| 재시작 복구 | | | |

### D. 마이그레이션 결과

| 항목 | 결과 | 근거 |
|---|---|---|
| 스키마 생성 | | |
| 테스트 데이터 이전 | | |
| 행 수·관계 검증 | | |
| checksum 검증 | | |
| rollback | | |

### E. 발견 위험과 다음 단계

각 위험의 심각도, 영향, 재현 방법 및 권장 조치를 기록한다. 다음 단계는 운영 전환 가능, adapter 보완, migration 보완 또는 운영 전환 중단 중 하나로 판정한다. 운영 전환은 별도 승인 없이 실행하지 않는다.

## 17. 실행 지시

먼저 1단계 읽기 전용 구조 조사부터 수행한다. 조사 결과와 변경 계획을 보고한 후 치명적 충돌이 없을 때만 adapter 보완과 테스트 DB 드라이런을 진행한다.

비밀번호나 연결 문자열을 대화창에 요구하지 말고 사용자가 로컬 .env에 직접 입력할 변수 이름과 위치만 안내한다. 테스트 DB 연결정보가 없으면 구조 분석·adapter 설계·테스트 준비까지만 수행하고 실제 통합시험은 BLOCKED로 보고한다.
