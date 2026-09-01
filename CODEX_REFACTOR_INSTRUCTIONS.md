# CODEX_REFACTOR_INSTRUCTIONS.md
# Codex CLI 실행용 작업 지시서

## 역할

당신은 기존의 안정적인 로컬 설교 작성기
"Sermon LM Studio V40.9.1"을 안전하게 리팩터링하는
수석 Python/FastAPI 엔지니어다.

목표는 기능 추가가 아니다.

현재 동작을 보존하면서
유지보수성을 높이는 것이 목표다.

---

# 이번 작업 범위

이번 실행에서는 오직 다음만 수행하라.

```text
PHASE 0 — Baseline 검사
PHASE 1A — config/constants 분리 계획
PHASE 1B — LM Studio Provider 분리 계획
```

중요:

처음 실행에서는 코드 수정하지 말고 분석만 수행하라.

---

# STEP 1 — 프로젝트 검사

다음을 확인한다.

- 디렉터리 구조
- app/core.py
- app/main.py
- LM Studio Client
- SQLite 관련 함수
- RAG 함수
- Prompt 관련 함수
- Sermon generation 함수
- Backup/Restore
- 테스트 구조

---

# STEP 2 — Baseline 테스트

전체 pytest를 실행한다.

기대 기준:

```text
212 passed
```

다르면 즉시 중단하고 보고한다.

---

# STEP 3 — 의존 관계 분석

app/core.py 안의 함수와 클래스를 다음 카테고리로 분류한다.

```text
CONFIG
DATABASE
BIBLE
ORIGINAL_LANGUAGE
DOCTRINE
PROJECT
SERMON
LMSTUDIO
RAG
PROMPT
QUALITY
AUDIT
BACKUP
UTILITY
```

각 항목에 대해:

```text
함수/클래스
현재 위치
호출하는 파일
호출되는 함수
DB 의존성
LM Studio 의존성
이동 위험도
권장 목적지
```

를 표로 작성한다.

---

# STEP 4 — 순환 참조 위험 분석

core.py를 분리할 경우 예상되는 import cycle을 분석한다.

특히:

```text
core
↔ database
↔ sermon
↔ rag
↔ provider
```

사이의 순환 참조 가능성을 확인한다.

코드를 수정하지 말고
의존 관계 그래프를 작성한다.

---

# STEP 5 — LM Studio 분석

다음을 확인한다.

- API base URL
- /v1/models
- /v1/chat/completions
- streaming
- reasoning_content
- timeout
- model selection
- health check
- localhost validation
- exception handling

다음 동작을 절대 약화시키지 않는다.

```text
LM Studio 장애
→ LM Studio 기능 오류
→ 전체 FastAPI 서버는 계속 실행
```

---

# STEP 6 — 분리 계획 작성

첫 리팩터링 후보는 반드시 작은 단위로 제한한다.

추천 순서:

```text
1. constants.py
2. config.py
3. providers/lmstudio.py
```

한 번에 DB와 RAG와 Sermon을 같이 이동하지 않는다.

---

# STEP 7 — 보고서 생성

다음 파일을 생성한다.

```text
reports/
PHASE0_BASELINE_REPORT.md
CORE_DEPENDENCY_MAP.md
LMSTUDIO_PROVIDER_REFACTOR_PLAN.md
```

단, 기존 소스는 변경하지 않는다.

---

# 코드 수정 금지

이번 실행에서는 다음 파일을 변경하지 않는다.

```text
app/core.py
app/main.py
data/*
tests/*
templates/*
static/*
```

분석 보고서만 생성한다.

---

# 다음 실행 허용 조건

다음 조건을 모두 만족하면
PHASE 1 실제 리팩터링을 제안할 수 있다.

- baseline test 정상
- 212 passed 이상
- dependency graph 작성
- import cycle 분석 완료
- LM Studio Provider boundary 확정
- rollback 방법 작성

---

# 출력 보고 형식

```markdown
# 분석 완료 보고

## 기준 버전

## 테스트 결과

## 현재 구조

## 가장 위험한 결합

## 안전하게 먼저 분리할 코드

## 지금 이동하면 안 되는 코드

## 예상 Import Cycle

## LM Studio Provider 경계

## Rollback 계획

## 다음 실행용 명령/프롬프트
```

---

# 최종 원칙

"동작하는 코드를 재작성하지 말고,
검증 가능한 작은 단위로 이동하라."