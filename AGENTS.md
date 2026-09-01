# AGENTS.md
# Sermon LM Studio V40.9.1 안전 리팩터링 규칙

## 1. 프로젝트 목적

이 프로젝트는 LM Studio 기반의 로컬 성경 근거 설교 작성기이다.

현재 기준 버전:
- 제품 내부 버전: V40.9.1
- 원본 폴더명: sermon-lmstudio-v1_6
- 운영 환경: Windows 10/11
- 주요 AI Provider: LM Studio
- 기본 LM Studio API: http://127.0.0.1:12345/v1
- 주 데이터베이스: SQLite
- 현재 자동 테스트 기준선: 212 passed

이 프로젝트에서 가장 중요한 목표는 새로운 기능 추가가 아니라,
현재 정상 기능을 보존하면서 구조적 복잡성을 줄이는 것이다.

---

## 2. 절대 원칙

### 2.1 한 번에 대규모 리팩터링 금지

다음 작업을 한 번에 수행하지 말 것.

- app/core.py 전체 재작성
- app/main.py 전체 재작성
- SQLite → PostgreSQL 즉시 전환
- 현재 RAG 시스템 전체 삭제
- 기존 LM Studio Client 전체 교체
- 전체 UI 프레임워크 교체
- 전체 Prompt 구조 동시 교체

반드시 작은 단위로 변경한다.

---

## 3. 작업 시작 전 필수 검사

모든 변경 전에 다음을 수행한다.

1. 현재 Git 상태 확인
2. 현재 브랜치 확인
3. 현재 제품 버전 확인
4. 테스트 전체 실행
5. 테스트 결과 저장
6. 변경 파일 목록 기록

기준선은 반드시 다음이어야 한다.

```text
212 passed
```

기준선 테스트가 실패하면 리팩터링을 시작하지 말고
실패 원인을 먼저 보고한다.

---

## 4. 코드 수정 규칙

### 4.1 기존 동작 유지

리팩터링 단계에서는 기능을 변경하지 않는다.

특히 다음 동작을 유지한다.

- LM Studio 연결
- LM Studio 모델 목록 조회
- Streaming generation
- reasoning_content 처리
- 설교 생성
- 설교 시간 보정
- 성경 본문 검증
- Evidence Packet
- Preflight
- 원어 데이터
- 번역본 비교
- RAG
- NotebookLM import/export
- 백업/복원
- DOCX/PDF/Markdown/HTML 출력
- Project 저장
- Audit

---

## 5. LM Studio 보호 규칙

LM Studio Provider는 반드시 localhost 기반으로 유지한다.

허용 기본 주소:

```text
http://127.0.0.1:12345/v1
```

또는 사용자가 명시적으로 설정한 localhost 주소.

다음 변경 금지:

```text
0.0.0.0
```

에 LM Studio를 직접 공개하지 않는다.

LM Studio 연결 실패가 전체 애플리케이션 종료로 이어져서는 안 된다.

Provider 장애는 기능 단위 오류로 처리한다.

---

## 6. 성경 근거 보호 규칙

다음 원칙을 절대 약화시키지 않는다.

- 중심 본문이 DB에 없으면 근거 기반 설교 생성 차단
- 본문 범위가 불완전하면 경고 또는 생성 차단
- 원어 자료와 번역본 자료를 구분
- 외부 Notebook 연구자료를 성경 DB의 확정 근거로 자동 승격하지 않음
- Evidence Packet 출처 metadata 유지
- 설교 생성 후 품질검사 유지

---

## 7. 데이터베이스 규칙

현재 리팩터링 범위에서는 SQLite를 유지한다.

금지:

- PostgreSQL 강제 전환
- 기존 DB schema의 대규모 변경
- 기존 테이블 삭제
- 데이터 마이그레이션 없는 schema 변경

DB 변경이 필요한 경우:

1. migration 작성
2. 기존 DB 백업
3. migration test 작성
4. rollback 방법 작성

---

## 8. RAG 규칙

현재 RAG를 삭제하지 않는다.

1차 목표:

```text
기존 Semantic Search 유지
+
SQLite FTS5 추가
+
Hybrid Search
+
RRF 병합
```

기존 검색 결과와 새 검색 결과를 동일 질문 세트로 비교한다.

기존 결과보다 명백히 나빠지면 새 방식을 기본값으로 전환하지 않는다.

---

## 9. 리팩터링 순서

다음 순서를 반드시 지킨다.

### Phase 0
Baseline 고정

### Phase 1
app/core.py 분리

### Phase 2
app/main.py Router 분리

### Phase 3
Prompt 분리

### Phase 4
SQLite FTS5 도입

### Phase 5
RRF Hybrid RAG

### Phase 6
Job / Progress 구조

### Phase 7
UI Workflow 단순화

### Phase 8
Provider 확장 검토

각 Phase 완료 후 전체 테스트를 실행한다.

---

## 10. core.py 분리 기준

목표 구조:

```text
app/
├─ core/
│  ├─ config.py
│  └─ constants.py
├─ repositories/
│  ├─ bible.py
│  ├─ sermon.py
│  ├─ doctrine.py
│  └─ settings.py
├─ providers/
│  ├─ base.py
│  └─ lmstudio.py
├─ rag/
│  ├─ lexical.py
│  ├─ semantic.py
│  └─ hybrid.py
├─ sermon/
│  ├─ research.py
│  ├─ outline.py
│  ├─ generator.py
│  ├─ quality.py
│  └─ audit.py
└─ prompts/
   ├─ outline.py
   ├─ sermon.py
   ├─ resize.py
   └─ revision.py
```

단, 실제 코드 분석 결과 더 안전한 구조가 있으면
기존 import 경로와 테스트를 보존하는 범위에서 조정 가능하다.

---

## 11. main.py Router 분리

목표:

```text
app/routers/
├─ health.py
├─ lmstudio.py
├─ bible.py
├─ original_language.py
├─ rag.py
├─ sermon.py
├─ projects.py
├─ backup.py
├─ notebooklm.py
└─ export.py
```

FastAPI main.py는 가능한 한 다음 역할만 유지한다.

- app 생성
- middleware
- router 등록
- startup/shutdown
- static/templates 연결

---

## 12. 테스트 정책

작은 변경 후 관련 테스트 실행.

Phase 종료 후 전체 테스트 실행.

전체 테스트가 다음보다 나빠지면 Phase 완료 금지.

```text
212 passed
```

새 테스트가 추가된 경우:

```text
212 + 추가 테스트 passed
```

이어야 한다.

---

## 13. 실패 시 행동

테스트 실패 시:

1. 추가 변경 중단
2. 실패한 테스트 목록 출력
3. 변경 파일 목록 출력
4. 원인 분석
5. 최소 수정
6. 다시 테스트

연속 3회 수정 후에도 실패하면
추가 변경을 중단하고 보고한다.

---

## 14. 파일 삭제 규칙

사용자 승인 없이 삭제 금지:

- data/
- backups/
- exports/
- tests/
- prompts/
- Bible source
- original language source
- Notebook research files
- SQLite DB
- migration files

---

## 15. 배포 최적화

.venv는 배포 ZIP에서 제외하는 것을 기본으로 한다.

단 개발 환경 자체에서는 삭제하지 않는다.

배포 패키지에는 필요 시 다음을 포함한다.

```text
app/
static/
templates/
tests/
requirements.txt
requirements.lock
launcher.py
start.bat
README.md
VERSION.txt
```

---

## 16. 작업 완료 보고

각 Phase 완료 후 반드시 다음 형식으로 보고한다.

```markdown
# Phase 완료 보고

## 변경 목적

## 변경 파일

## 변경 내용

## 기존 기능 영향

## 테스트
- 관련 테스트:
- 전체 테스트:
- 결과:

## 발견된 문제

## 남아 있는 위험

## Rollback 방법

## 다음 권장 단계
```

---

## 17. 최우선 목표

이 프로젝트의 최우선 목표는 다음이다.

> 정상적으로 작동하는 기존 설교 작성기를 보존하면서
> 유지보수성과 확장성을 높인다.

새로운 기능보다 안정성을 우선한다.