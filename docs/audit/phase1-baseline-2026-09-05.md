# Phase 1 Baseline 고정 보고서

기준일: 2026-09-05  
브랜치: `refactor/phase1-baseline-20260905`  
기준 커밋: `66a5321 feat: organize sermon workflow feature map`  
제품 버전: `40.9.10`

## 기준선 고정 범위

이번 단계에서는 소스 코드, DB schema, RAG backend, MinIO object, 운영 credential을
변경하지 않았다. 비교·롤백에 필요한 메타데이터만 기록했다. `data/`, `backups/`,
`exports/`, `fonts/`와 사용자가 추가한 지시서 파일은 커밋 대상에서 제외했다.

## Git 기준선

- 기준 브랜치: `main`
- 작업 브랜치: `refactor/phase1-baseline-20260905`
- 기준 커밋: `66a5321`
- 기준 테스트: `411 passed, 19 skipped`
- 외부 통합 skip: PostgreSQL/pgvector/MinIO readiness 및 migration 관련 19건

## 주요 파일 SHA-256

| 파일 | 크기 | SHA-256 |
|---|---:|---|
| `VERSION.txt` | 9 bytes | `9b5f73c82f2cbc0052ed581517a9cfd6e97ef07e3210bdbd3cc122b2a5363866` |
| `templates/index.html` | 87,662 bytes | `54c0df1c87b13cbd97ce9a843ff2e6d6be2088f301d42c6cabef99150e9ac5dd` |
| `static/v2.css` | 61,977 bytes | `ff4feb418667d039e0f23ac2c42bb19f4de5965ac9e7ba8e60932890667fe80d` |
| `static/app.js` | 176,892 bytes | `e05aa0aa14099de04b0e57cae862c8eab70c2850e5c9ff124750782672b2f08e` |
| `data/bible.db` | 524,210,176 bytes | `b58e1da0d6ac49fae6912498774adbcc169f6dd89e65d4df345e164a88d7eb7f` |
| `backups/sermon_backup_20260905_001315_808451.zip` | 146,403,508 bytes | `5e1bafba46ec99ace87ca8f2a8d333d01e8899f073dad3cabf2c166fafa4c17a` |

## SQLite 읽기 전용 inventory

`data/bible.db`를 `mode=ro`로 열어 schema를 변경하지 않고 확인했다.

- 사용자 DB 테이블 수: 31개
- 설교 프로젝트: 2개
- 설교 버전: 12개
- `original_word_notes`: 412,309건
- 주요 보존 테이블: `sermons`, `sermon_versions`, `sermon_reviews`,
  `sermon_version_locks`, `source_snapshots`, `rag_embeddings`, `rag_fts` 관련 구조,
  `original_word_notes`, `original_pronunciations`, `greek_nt_tokens`,
  `doctrine_*`, `schema_migrations`
- 현재 확인된 스키마 변경: 없음

## 검색·운영 기준선

- 기본 RAG backend: SQLite
- `RAG_PGVECTOR_CAPABILITY_VERIFIED=false`
- SQLite fallback: 활성 정책
- LM Studio: `http://127.0.0.1:12345/v1`
- 애플리케이션: `http://127.0.0.1:8000`
- MinIO: `.env.example` 기준 기본 비활성
- 운영 pgvector credential: 임의 생성하지 않음
- 기존 pgvector 관련 보존 artifact: `backups/pgvector_prod_pre_reindex_20260905.dump`,
  `backups/pgvector_prod_post_reindex_20260905.dump`

## API·UI 비교 기준

- route decorator 확인 수: 102개
- 호환 route가 `app/main.py`에 남아 있고 기능별 router도 동시에 존재한다.
- 기존 UI 이동 계약: `data-jump`, `workflowRailSteps`, `optional-panel`/`simple-ui`
- 구조화 UI 기준: `architecturePanel`과 기존 작업 panel ID를 모두 유지한다.

## 샘플 및 출력 기준

현재 DB에서 확인된 설교 프로젝트와 버전의 원문을 별도 복사하거나 외부로 전송하지
않았다. 개인정보·목회자료 보존 원칙에 따라 샘플 내용 대신 DB 개수와 파일 hash를
기준선으로 사용한다. 기존 출력물은 `exports/`에 보존하며 정리·삭제하지 않았다.

## Gate 1 판정

- Git 기준선: 완료
- 롤백용 별도 브랜치: 완료
- DB 읽기 전용 inventory: 완료
- 기존 백업 존재 및 hash 기록: 완료
- MinIO 운영 백업: **운영 설정 대기** (`MINIO_ENABLED=false`)
- 운영 pgvector 전환: **진행하지 않음**
- 전체 회귀 기준: 통과 (`411 passed, 19 skipped`)
- Phase 2 진행 가능 여부: 가능하나 `core.py`/`main.py` 일괄 재작성 금지

## Rollback 방법

1. 현재 브랜치 변경을 중단하고 기준 커밋 `66a5321`을 확인한다.
2. 이후 Phase 변경은 별도 커밋 단위로 되돌린다.
3. DB 복구가 필요한 경우 기존 통합 백업 ZIP 또는 승인된 DB 백업 절차를 먼저
   검증하고, 사용자에게 확인한 뒤 복구한다.
4. 운영 pgvector/MinIO는 readiness와 credential이 확인되기 전까지 전환하지 않는다.

## 다음 권장 단계

Phase 2 `Repository/Service/Router 구조 정리 완결`로 진행한다. 단, 먼저 변경 예정
파일과 route contract를 보고하고, 한 기능 단위만 facade에서 추출한 뒤 관련 테스트와
전체 회귀 테스트를 통과시켜야 한다.
