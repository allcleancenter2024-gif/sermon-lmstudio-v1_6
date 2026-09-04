# PostgreSQL·pgvector 단계적 전환 검증 Runbook

## 문서 목적

이 문서는 SQLite 기반 RAG를 보존하면서 PostgreSQL·pgvector를 격리 검증하고, 검색 결과가 기준선을 만족한 경우에만 운영 전환·운영·복구를 수행하기 위한 절차입니다.

현재 운영 기본값은 다음과 같습니다.

| 항목 | 현재 정책 |
|---|---|
| 운영 RAG | PostgreSQL·pgvector Semantic Search, SQLite FTS5/Hybrid 및 Semantic Search fallback 유지 |
| pgvector | 별도 운영 DB `127.0.0.1:15434`에서 활성화 |
| 임베딩 모델 | `text-embedding-nomic-embed-text-v1.5` |
| 임베딩 차원 | 768 |
| SQLite 원본 | 읽기 전용 기준선 및 장애 fallback으로 보존 |
| 운영 전환 | 2026-09-05 승인·검증 후 활성화 |

## 단계별 전환 게이트

### Gate 0: 실행 환경 확인

다음 조건을 모두 만족해야 합니다.

1. Docker Desktop이 실행 중입니다.
2. 테스트 PostgreSQL과 MinIO가 `healthy` 상태입니다.
3. 테스트 DB 이름은 `sermon_pgvector_test`입니다.
4. 운영 DB와 테스트 DB의 연결 문자열이 다릅니다.
5. MinIO 버킷은 `sermon-documents-test`입니다.
6. 운영 버킷과 테스트 버킷의 자격증명이 분리되어 있습니다.

### Gate 1: pgvector capability

다음 조건을 확인합니다.

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
```

`vector`가 없으면 pgvector 검색 검증을 중단합니다. PostgreSQL 연결 성공만으로 통과 처리하지 않습니다.

### Gate 2: 검색 결과 비교

격리된 테스트 DB에 실제 SQLite 임베딩 샘플을 적재하고, 로컬 LM Studio에서 생성한 동일 질의 벡터로 비교합니다.

- 샘플 수: 256건
- 질의 수: 4건
- 비교 범위: 상위 10개 ID 순서
- 허용 점수 오차: `1e-5`
- 기준선: 기존 SQLite cosine similarity

다중 질의에서 하나라도 ID 순서 또는 점수 기준을 만족하지 못하면 pgvector 전환을 차단합니다.

### Gate 3: 운영 전환 승인 또는 운영 재검증

신규 전환은 Gate 0~2를 통과해도 자동으로 수행하지 않습니다. 다음 자료를 별도로 확인해야 합니다.

- 전체 데이터 재색인 예상 시간
- 임베딩 모델·차원·버전 일치 여부
- SQLite 대비 검색 품질 비교 보고서
- 백업 파일과 복구 테스트 결과
- 장애 시 SQLite 복귀 확인
- 관리자 승인 기록

### Gate 4: 전체 corpus canary readiness audit

운영 전환 전에는 격리 DB와 운영 대상 DB에서 readiness audit를 실행합니다. 운영 대상 audit는 SQLite 전체 corpus를 순위 기준선으로 사용합니다. Audit는 다음을 모두 통과해야 `PASS`를 반환합니다.

- `rag_pgvector_v1` migration ID 기록 존재
- canary SQLite 원본 건수와 pgvector model별 적재 건수 일치
- 각 질의의 상위 결과 ID 순서 완전 일치
- 각 pgvector 검색 지연시간이 설정된 예산 이내

어느 하나라도 실패하면 결과는 `BLOCKED`이며, backend 전환이나 환경변수 변경을 수행하지 않습니다.

## 검증 실행

### 운영 전용 service 준비

테스트 DB `127.0.0.1:15433`은 운영에 사용하지 않습니다. 운영 DB는 별도 Compose와 `127.0.0.1:15434`를 사용합니다.

```powershell
Copy-Item config\pgvector-prod.env.example config\pgvector-prod.env
docker compose --env-file config\pgvector-prod.env -f docker-compose.pgvector-prod.yml up -d
docker compose --env-file config\pgvector-prod.env -f docker-compose.pgvector-prod.yml ps
```

복사한 `config\pgvector-prod.env`에만 고유한 `POSTGRES_RAG_PROD_PASSWORD`를 입력합니다.

운영 service 생성만으로 RAG backend가 바뀌지 않습니다. migration, 전체 적재, readiness, canary, 백업 및 SQLite fallback 검증이 모두 통과한 경우에만 `RAG_BACKEND=postgres_pgvector`와 `RAG_PGVECTOR_CAPABILITY_VERIFIED=true`로 변경합니다. `RAG_PGVECTOR_FALLBACK_TO_SQLITE=true`는 항상 유지합니다.

테스트 서비스는 다음 Compose 파일에서 별도 관리합니다.

```powershell
docker compose -f docker-compose.minio-test.yml up -d postgres-pgvector-test
docker compose -f docker-compose.minio-test.yml ps
```

실제 비교는 명시적인 프로세스 환경변수를 설정한 경우에만 실행합니다.

```powershell
$env:RUN_PGVECTOR_SEARCH_COMPARISON = "1"
$env:PGVECTOR_DATABASE_URL = "postgresql://sermon_user:<TEST_PASSWORD>@127.0.0.1:15433/sermon_pgvector_test"
.\.venv\Scripts\python.exe -m pytest -q tests\test_pgvector_search_comparison_integration.py
```

readiness audit 통합 검증은 별도 플래그로 실행합니다.

```powershell
$env:RUN_PGVECTOR_READINESS_INTEGRATION = "1"
$env:PGVECTOR_DATABASE_URL = "postgresql://sermon_user:<TEST_PASSWORD>@127.0.0.1:15433/sermon_pgvector_test"
.\.venv\Scripts\python.exe -m pytest -q tests\test_pgvector_readiness_integration.py
```

일반 회귀 테스트는 pgvector 환경변수 없이 실행하여 운영 기본값을 확인합니다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 백업 및 rollback

### 운영 전환 전

1. 기존 SQLite DB를 애플리케이션 백업 기능으로 백업합니다.
2. 백업 ZIP의 SHA-256과 SQLite `quick_check` 결과를 보관합니다.
3. 백업 파일명, 제품 버전, migration 상태를 전환 기록에 남깁니다.
4. 운영 환경변수는 변경하지 않은 상태로 rehearsal을 먼저 수행합니다.

### pgvector rehearsal rollback

rehearsal 실패 시 다음 순서로 되돌립니다.

1. pgvector 테스트 적재 작업을 중단합니다.
2. 테스트 DB의 비교 테이블만 비웁니다.
3. 테스트 컨테이너를 중지합니다.

```powershell
docker compose -f docker-compose.minio-test.yml stop postgres-pgvector-test
```

4. 기존 SQLite RAG를 계속 사용합니다.
5. 운영 `RAG_BACKEND` 또는 운영 DB 연결정보는 변경하지 않습니다.

### 운영 전환 후 rollback 조건과 절차

다음 중 하나라도 발생하면 운영 전환을 즉시 중단하고 SQLite 기준선으로 복귀합니다.

- 검색 결과 ID 일치율 기준 미달
- 임베딩 차원 또는 모델 버전 불일치
- pgvector extension 또는 인덱스 오류
- 검색 지연시간 기준 초과
- 설교 근거 본문 누락 또는 출처 metadata 손실
- DB 또는 MinIO 원본 복구 검증 실패

운영 복귀는 다음 순서로 수행합니다.

1. `config/pgvector-prod.env`에서 `RAG_BACKEND=sqlite`, `RAG_PGVECTOR_CAPABILITY_VERIFIED=false`로 변경합니다.
2. `docker compose -f docker-compose.yml up -d --build sermon-lmstudio`로 애플리케이션만 재시작합니다.
3. `/api/runtime` health와 SQLite Semantic Search를 확인합니다.
4. PostgreSQL 덤프는 별도 보존하고, SQLite DB·원본 테이블·pgvector 컨테이너를 삭제하거나 덮어쓰지 않습니다.

pgvector DB 자체의 복구가 필요할 때만 사전 검증된 `pg_restore` 덤프를 **별도 복구 DB**에 먼저 복원하여 검증한 뒤 운영 복구 여부를 결정합니다.

## 현재 검증 기록

| 검증일 | 결과 |
|---|---|
| 2026-09-04 | pgvector capability 통과 |
| 2026-09-04 | 실제 LM Studio 임베딩 단일 질의 비교 통과 |
| 2026-09-04 | 실제 LM Studio 임베딩 다중 질의 비교 통과 |
| 2026-09-04 | 전체 회귀 `386 passed, 14 skipped` |
| 2026-09-05 | migration·증분 재색인·canary readiness audit 통과 |
| 2026-09-05 | SQLite 31,098건 → 운영 pgvector 31,098건 전체 적재 완료 |
| 2026-09-05 | 전체 corpus canary 통과: 4개 질의 상위 10개 순위 일치, 최대 42.161ms |
| 2026-09-05 | PostgreSQL 백업·덤프 목록 검증 및 SQLite fallback 4.286초 통과 |
| 2026-09-05 | `postgres_pgvector` 주 경로 활성화, 실행 컨테이너 health 확인 |

## 경고 및 제한

- 이 문서는 2026-09-05에 완료된 운영 전환과 이후 운영·복구 절차를 함께 기록합니다. 신규 환경 전환은 여전히 별도 승인이 필요합니다.
- 256건 표본은 빠른 사전 점검용이며, 운영 전환 기록은 SQLite 전체 31,098건을 순위 기준선으로 검증했습니다.
- 현재 애플리케이션의 실제 RAG 검색 주 경로는 PostgreSQL·pgvector이며 SQLite fallback은 활성 상태입니다.
- 비밀번호·Secret Key를 문서, Git, 로그에 기록하지 않습니다.
- 운영 DB와 운영 MinIO에 테스트 플래그를 사용하지 않습니다.
- 테스트용 Docker 볼륨을 운영 데이터 저장소로 사용하지 않습니다.
- `config/pgvector-prod.env`는 Git에 추가하지 않으며, 실제 비밀번호를 채팅·문서·로그에 기록하지 않습니다.
