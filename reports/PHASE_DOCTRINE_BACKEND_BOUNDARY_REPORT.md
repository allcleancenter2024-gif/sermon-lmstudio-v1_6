# Doctrine backend contract 연결 보고서

## 판정

**조건부 완료 — 경계 연결 완료, 전체 전환 보류**

doctrine 기능군의 다음 migration 단계를 위해 명시적 backend factory를 추가했다. 기본 실행은 기존 SQLite로 유지하고, PostgreSQL은 명시적인 `DB_BACKEND=postgres`와 테스트 `DATABASE_URL`이 있을 때만 선택된다.

## 변경 파일

- `app/doctrine_backend.py`
- `tests/test_doctrine_backend.py`
- `reports/PHASE_DOCTRINE_BACKEND_BOUNDARY_REPORT.md`

## 결과

| 항목 | 결과 |
|---|---|
| 기존 SQLite 기본 선택 | PASS |
| PostgreSQL 명시 선택 | PASS |
| PostgreSQL URL 누락 차단 | PASS |
| 기존 doctrine 함수 동작 보존 | PASS |
| 기존 SQLite adapter 제거 | 없음 |
| 운영 DB 접근 | 없음 |
| 운영 MinIO 변경 | 없음 |
| 전체 애플리케이션 전환 | 보류 |

## 구조

`create_doctrine_backend()`가 adapter와 `DoctrineRepository`를 함께 반환한다. 이후 기능별 repository가 이 factory를 주입받을 수 있지만, 현재 `snapshot_source`, `doctrine_processing`, `doctrine_workflow`의 기존 SQLite 직접 접근은 안전을 위해 아직 자동 교체하지 않았다.

## 테스트

- backend 관련 테스트: `3 passed, 1 skipped`
- 전체 회귀: `337 passed, 8 skipped`
- 의존성 검사: `No broken requirements found`
- compileall: PASS

## 안전성

- 기본 backend는 `existing` SQLite
- 잘못된 backend 또는 PostgreSQL URL 누락은 오류
- 운영 DB·운영 MinIO 미접근
- 운영 `DATABASE_URL` 변경 없음
- 기존 사용자 변경사항과 겹치는 대규모 파일 재작성 없음

## 남은 위험

- doctrine 처리·workflow·RAG의 SQLite 직접 접근이 남아 있다.
- 현재 factory는 경계 연결 단계이며 애플리케이션 전체의 PostgreSQL 동작을 보장하지 않는다.
- 다음 기능군 연결 전에는 각 repository의 timestamp, JSONB, foreign key, transaction 회귀를 다시 실행해야 한다.

## Rollback

- `DB_BACKEND`를 설정하지 않거나 `existing`으로 설정하면 기존 SQLite 경로를 유지한다.
- 새 factory와 테스트 파일을 되돌려도 기존 DB·MinIO 데이터는 변경되지 않는다.

## 다음 권고

다음 단계는 `doctrine_processing` 기능군을 이 factory에 연결하는 작은 변경이다. 기존 `snapshot_source`와 workflow는 그대로 두고, 문서 metadata read/update부터 단계적으로 전환한다.
