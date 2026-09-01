# REFACTOR_PLAN.md
# Sermon LM Studio V40.9.1 단계별 리팩터링 계획

## 1. 현재 판단

현재 프로그램은 기능적으로 상당히 안정되어 있으며,
자동 테스트 212개가 통과하는 상태다.

가장 큰 문제는 기능 부족이 아니라 구조적 복잡성이다.

주요 복잡도:

- app/core.py 약 2,893줄
- app/main.py 약 1,644줄
- API Route 집중
- DB/RAG/Provider/Prompt/설교 생성 로직이 core.py에 집중
- 장시간 AI 생성이 HTTP 요청 생명주기에 묶임
- Hybrid RAG의 lexical 부분이 단순 LIKE 중심

---

# PHASE 0 — Baseline 고정

## 목적

변경 전 상태를 명확히 저장한다.

## 작업

- Git branch 생성
- 현재 버전 기록
- 전체 테스트 실행
- 현재 API Route 목록 저장
- DB schema dump
- 주요 UI 화면 캡처
- LM Studio 연결 테스트
- 샘플 설교 3건 생성 결과 저장

권장 브랜치:

```text
refactor/v40-modularization
```

완료 조건:

```text
212 passed
```

---

# PHASE 1 — core.py 모듈화

## 목적

가장 큰 유지보수 위험을 제거한다.

## 우선 추출 순서

### 1A. 설정/상수

```text
app/core/config.py
app/core/constants.py
```

### 1B. LM Studio Provider

```text
app/providers/base.py
app/providers/lmstudio.py
```

기존 public API는 유지한다.

### 1C. Repository

```text
app/repositories/
```

대상:

- Bible
- Sermon
- Doctrine
- Settings
- Project

### 1D. Sermon Service

```text
app/sermon/
```

대상:

- research
- outline
- generation
- resizing
- validation
- audit

### 1E. RAG

```text
app/rag/
```

대상:

- embedding
- semantic search
- lexical search
- hybrid

완료 조건:

- 기존 테스트 모두 통과
- API 응답 형식 변화 없음
- UI 변경 없음

---

# PHASE 2 — main.py Router 분리

## 목적

FastAPI endpoint를 기능별로 격리한다.

목표 구조:

```text
app/routers/
├─ health.py
├─ lmstudio.py
├─ bible.py
├─ original_language.py
├─ rag.py
├─ sermon.py
├─ projects.py
├─ notebooklm.py
├─ backup.py
└─ export.py
```

main.py 목표:

```python
app = FastAPI(...)
app.include_router(...)
```

중심으로 단순화.

완료 조건:

- Route URL 변화 없음
- request/response schema 변화 없음
- 전체 테스트 통과

---

# PHASE 3 — Prompt 분리

## 목적

Python 코드와 Prompt 정책을 분리한다.

권장:

```text
app/prompts/
├─ outline.py
├─ sermon.py
├─ resize.py
├─ revision.py
└─ quality.py
```

Prompt에는 version metadata를 포함한다.

예:

```text
SERMON_PROMPT_VERSION = "2026-08-v1"
```

Generation Audit에 prompt version 저장 권장.

---

# PHASE 4 — SQLite FTS5

## 목적

현재 LIKE 검색을 실제 Full Text Search로 개선한다.

구조:

```text
Bible/RAG document
      ↓
SQLite FTS5
```

기존 lexical search는 fallback으로 유지.

완료 조건:

- 기존 검색 테스트 통과
- FTS5 unavailable 환경 fallback
- 검색 성능 비교 보고

---

# PHASE 5 — RRF Hybrid RAG

## 목표 구조

```text
Query
 ├─ Semantic Search
 └─ FTS5 Search
        ↓
      RRF
        ↓
   Top Evidence
```

추천 metadata:

```text
document_id
source_name
reference
page
chunk_id
semantic_rank
lexical_rank
rrf_score
retrieval_type
```

기존 75/25 weighted 방식은 비교용으로 잠시 유지한다.

동일 질문 세트 A/B 테스트 후 기본 전략을 결정한다.

---

# PHASE 6 — Job / Progress

## 대상

장시간 작업:

- 설교 생성
- 대규모 RAG indexing
- Bible import
- Original language import
- Backup
- Restore

Job 상태:

```text
queued
running
researching
outlining
generating
resizing
validating
completed
failed
cancelled
```

필수 field:

```text
job_id
progress
current_stage
started_at
updated_at
error_message
retry_count
```

초기에는 Celery/Redis 없이
in-process Job Manager로 시작하는 것을 권장한다.

---

# PHASE 7 — UI Workflow 단순화

사용자 주요 Workflow:

```text
1. 준비
2. 본문 입력
3. 본문 연구
4. 3대지
5. 설교 생성
6. 검토
7. 저장/출력
```

관리 메뉴로 분리:

```text
성경 자료
원어 자료
RAG 관리
NotebookLM
백업
환경설정
```

목표:

사용자가 설교 하나를 작성할 때
관리 기능을 매번 볼 필요가 없도록 한다.

---

# PHASE 8 — 확장

구조 안정화 후 검토:

```text
Ollama Provider
Tailscale
Optional Web Search
PostgreSQL
pgvector
```

현재 단계에서는 PostgreSQL 강제 전환하지 않는다.

---

# 완료 판단 기준

최종 리팩터링 성공 조건:

1. 기존 기능 유지
2. 212개 이상 테스트 통과
3. core.py 책임 대폭 감소
4. main.py Router 분리
5. LM Studio failure isolation 유지
6. Evidence/Preflight 정책 유지
7. SQLite 데이터 호환 유지
8. 백업/복원 호환 유지
9. UI 기본 Workflow 유지
10. Rollback 가능