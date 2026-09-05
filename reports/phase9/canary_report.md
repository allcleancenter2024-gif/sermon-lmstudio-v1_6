# Phase 9 Canary 비교 보고서

기준일: 2026-09-05

## 범위

운영 후보 PostgreSQL·pgvector와 기존 SQLite의 Bible RAG 검색을 비교했다. SQLite 원본은 읽기 전용으로 사용했으며, 테스트 DB(`15433`)는 운영 대상으로 사용하지 않았다.

## 데이터 기준선

| 항목 | SQLite | 운영 후보 pgvector | 결과 |
|---|---:|---:|---|
| passages | 31,098 | 31,098 | PASS |
| embeddings | 31,098 | 31,098 | PASS |
| orphan embeddings | 0 | 0 | PASS |
| duplicate passages | 0 | 0 | PASS |
| invalid dimensions | 0 | 0 | PASS |

## Bible canary

- 고정 embedding 질의: 3건
- Top-K: 5
- 결과 overlap: 모두 1.0
- rank match: 3/3
- latency: 20.959~32.672ms
- migration marker: `rag_pgvector_v1`
- 판정: PASS

## 전체 Evidence 영역 판정

운영 후보 PostgreSQL에는 현재 `rag_pgvector_passages`, `rag_pgvector_embeddings` 성경 검색 schema만 존재한다. 교단·신앙고백·주석 Evidence용 `doctrine_*` schema가 없어 해당 영역의 canary는 실행하지 않았다.

따라서 Phase 9 전체 canary 판정은 `BLOCKED`이며, pgvector를 primary backend로 전환하지 않는다.

## Fallback

pgvector 장애 시 SQLite fallback 계약 테스트: PASS (`15 passed` 관련 테스트 묶음).

## 다음 조건

교단·신앙고백·주석·설교문 감별기 Evidence의 저장·검색 경계를 먼저 결정하고 별도 migration/canary를 수행한 후 Phase 9 전체 Go/No-Go를 재판정한다.
