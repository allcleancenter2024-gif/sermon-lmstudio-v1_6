# Phase 0 최신 저장소 감사 보고서

감사 기준일: 2026-09-05  
대상: `sermon-lmstudio-v1_6`  
제품 버전: `40.9.10`  
브랜치: `main`  
최신 커밋: `66a5321 feat: organize sermon workflow feature map`

## 감사 범위와 변경 통제

마스터 작업지시서의 Phase 0에 따라 소스 코드, 데이터베이스, 운영 credential,
RAG backend, MinIO 설정은 변경하지 않았다. 감사 결과를 보존하기 위해 이 보고서
파일과 `docs/audit` 디렉터리만 추가했다. 기존 사용자 데이터, 백업, 출력물, 폰트,
원어 자료로 표시된 미추적 파일은 읽거나 커밋하지 않았다.

## 기준선

- Git: `main...origin/main` 동기화 상태
- 추적 파일 변경: 없음(감사 보고서 추가 전 기준)
- 전체 회귀 테스트: `411 passed, 19 skipped`
- 제품 Python 실행: `.venv`
- 기본 LM Studio: `http://127.0.0.1:12345/v1`
- 애플리케이션 로컬 주소: `http://127.0.0.1:8000`
- 지원 설교 시간: `15, 20, 25, 30분`

19개 skip은 pgvector, PostgreSQL, MinIO 등 명시적 외부 통합 플래그가 없는
환경에서 기존 정책에 따라 건너뛴 것이다. 실패 테스트는 없다.

## 현재 구조 지도

```text
app/
├─ core.py                         # 호환 facade와 기존 핵심 로직, 2,206줄
├─ main.py                         # FastAPI route와 호환 구현, 1,799줄
├─ application/                    # facade, profile, job/progress 계층
├─ repositories/                   # Bible, Sermon, Doctrine, Project, Settings, RAG
├─ providers/                      # Provider port, LM Studio, registry
├─ rag/                            # SQLite FTS5, semantic, hybrid/RRF, pgvector gate
├─ evidence/, grounding/           # evidence model, grounding audit/validator
├─ services/                       # 원어·설교·본문비평 application service
├─ routers/                        # auth, health, bible, doctrine, projects, exports, settings
├─ formatting/                     # 공통 문서 모델, renderer, quality/telemetry
└─ 원어·교리·백업·수집 모듈            # 기존 기능 유지 영역

templates/index.html + static/style.css + static/v2.css + static/app.js
└─ 단일 페이지 UI, 작업 메뉴, workflow rail, 설교 마법사, 관리/출력 패널
```

## 책임 분리 현황

### 완료 또는 사용 가능한 경계

- Settings, Bible, Sermon, Doctrine, Project, RAG Repository가 존재한다.
- Application facade가 기존 route와 내부 구현 사이의 호환 경계를 제공한다.
- `providers/base.py`, `providers/lmstudio.py`, `providers/registry.py`로 Provider
  계약과 LM Studio 구현이 분리되어 있다.
- `application/job_progress.py`, `job_registry.py`, `workflow_jobs.py`가 진행상태,
  취소, 실패 상태를 관리한다.
- Evidence/grounding 모델과 감사 흐름이 별도 모듈로 존재한다.
- `formatting` 계층이 Markdown/HTML/PDF/DOCX/HWPX 관련 공통 출력 경계를 제공한다.
- SQLite FTS5와 semantic/hybrid/RRF 검색이 있으며 기존 RAG를 보존하는 구조다.
- 원어 자료(SBLGNT, MorphGNT, Apparatus, OSHB 관련 흐름)와 공식 설치/검증 경로가
  기존 UI·서비스에 연결되어 있다.
- 최근 UI 변경으로 `architecturePanel`이 추가되었고, 준비 → 연구 → 근거 → 생성 →
  검토 → 출력·운영 흐름을 기존 패널로 연결한다.

### 부분 완료 또는 후속 구현 대상

- `core.py`와 `main.py`는 여전히 큰 호환 facade/route 집합이다. 즉시 전체 이동하면
  import cycle, 응답 contract 변경, 기존 테스트 회귀 위험이 있다.
- 마스터 지시서의 `app/modules/*` 최종 폴더 구조는 아직 실제 구조가 아니다.
- 감별기 독립 Domain/Rules/RAG/UI와 11개 범주 golden set은 현재 최종 구현으로
  확인되지 않는다.
- Claim/Citation/EvidenceSnapshot의 완전한 versioned persistence는 기존 Evidence
  및 Grounding 기능과 범위를 맞춰 별도 설계가 필요하다.
- Denomination/Audience/SermonFormat Profile은 application profile 계약이 있으나,
  마스터 지시서가 요구하는 완전한 versioned entity와 과거 승인본 재현 게이트는
  추가 확인 후 구현해야 한다.
- 공통 디자인 토큰·컴포넌트 폴더가 별도 `web/` 구조로 분리되어 있지 않다. 현재
  CSS와 단일 HTML의 점진적 추출이 안전하다.

## API와 Provider

`main.py`에 기존 호환 route가 다수 남아 있고, `routers/`에도 기능별 route가
등록되어 있다. 따라서 Phase 2에서 route를 이동할 때는 URL과 JSON schema를 먼저
contract로 고정해야 한다. `health`, `auth`, `settings`, `bible`, `doctrine`,
`projects`, `exports` router는 이미 존재하지만 모든 route가 완전히 `main.py` 밖으로
이동한 상태는 아니다.

LM Studio는 localhost 기본 주소를 유지하며, Provider 장애가 FastAPI 전체 종료로
이어지지 않도록 기존 contract와 failure isolation 테스트를 보존해야 한다. 자동
cloud fallback이나 외부 전송을 추가할 근거는 현재 감사에서 확인되지 않았다.

## DB·RAG·MinIO 운영 경계

- 기본 애플리케이션 DB와 Bible/RAG 저장은 SQLite 호환 경로를 사용한다.
- `RAG_BACKEND` 기본값은 `sqlite`이고 `RAG_PGVECTOR_CAPABILITY_VERIFIED` 기본값은
  `false`다.
- `RAG_PGVECTOR_FALLBACK_TO_SQLITE`는 `true`로 명시되어 있다.
- 운영 pgvector 전용 설정 예시는 `config/pgvector-prod.env.example`에 있으나,
  실제 운영 readiness를 감사 단계에서 자동 승인하지 않는다.
- MinIO는 `.env.example`에서 기본 비활성(`MINIO_ENABLED=false`)이며 테스트/운영
  prefix가 구분되어 있다.
- 테스트 PostgreSQL/pgvector를 운영 DB로 승격하거나, credential을 코드·기본값에
  채우는 구조는 확인하거나 수행하지 않았다.

## UI 구조와 충돌 위험

현재 UI는 기존 단일 페이지와 `workflowRailSteps`, `data-jump`, `simple-ui`/고급
기능 토글에 의존한다. 최근 추가된 기능 구조 패널은 기존 panel ID와 이동 함수를
재사용하므로 현재 구조와 충돌하지 않는다. 다만 마스터 지시서의 AppShell을 한 번에
도입하면 다음 위험이 있다.

1. 단일 페이지의 `optional-panel` 표시 규칙이 바뀌어 초보자 화면이 복잡해질 수 있다.
2. 기존 `data-jump` 및 workflow 상태 동기화가 끊길 수 있다.
3. 관리 기능을 실제 DOM에서 이동하면 기존 event binding과 저장 상태가 손상될 수 있다.
4. 모바일에서 고정 메뉴·진행상태·편집 영역이 겹칠 수 있다.

따라서 UI 개선은 기존 DOM ID와 이동 계약을 유지한 채 토큰·컴포넌트·반응형 수용
테스트를 단계적으로 추가해야 한다.

## 마스터 지시서 대비 변경 대상 후보

Phase 0 이후 가장 안전한 우선순위는 다음과 같다.

1. `tests/`에 API/Repository/Provider/Job contract 목록을 고정한다.
2. `app/core.py`에서 이미 분리된 Repository/Service 호출만 작은 facade 단위로
   추출하고, 한 번에 전체 재작성하지 않는다.
3. `app/main.py`의 route를 기존 router와 계약 테스트 단위로 하나씩 이동한다.
4. 현재 CSS에서 semantic token을 추출하고, 기존 클래스의 alias로 적용한다.
5. 현재 Job/Progress 흐름에 `discernment` stage를 추가하되 생성 API와 분리한다.
6. Profile/Evidence/Citation의 현재 저장 구조를 확인한 뒤 versioned migration을
   별도 Phase로 설계한다.
7. 운영 pgvector/MinIO는 실제 credential·readiness·복구 증거가 준비된 경우에만
   별도 운영 단계로 진행한다.
8. 감별기는 독립 rules/domain/application 계층과 golden set부터 만든다.

## 위험 순위

| 순위 | 위험 | 영향 | 통제 |
|---:|---|---|---|
| 1 | `core.py`/`main.py` 대규모 이동 | import·API 회귀 | 작은 facade 추출과 contract test |
| 2 | SQLite/운영 pgvector 혼합 | 데이터 손상·잘못된 검색 | 명시적 backend gate와 fallback |
| 3 | 단일 페이지 UI 전면 교체 | 입력·진행상태 손실 | 기존 ID/data-jump 보존 |
| 4 | 감별기 단일 Prompt 의존 | 오탐·근거 없는 낙인 | 규칙·문맥·근거·사람 검토 분리 |
| 5 | Profile 변경의 과거 승인본 영향 | 재현성 상실 | versioned snapshot 고정 |
| 6 | 외부 자료/Provider 자동 전송 | 개인정보·보안 위험 | localhost 우선, 명시 동의 |

## Phase 0 Gate 판정

- 코드 변경: 없음
- DB 변경: 없음
- 운영 credential 변경: 없음
- 전체 baseline 회귀: 통과 (`411 passed, 19 skipped`)
- 실제 구조 지도: 작성 완료
- 변경 최소 파일 후보: 확정
- 다음 단계 가능 여부: **가능하나 전면 수정은 금지**

## 권장 다음 단계

Phase 1인 baseline 고정 작업으로 진행한다. 먼저 현재 커밋과 감사 보고서를 보존하고,
API route 목록·schema 요약·DB 스키마 dump·샘플 출력 hash를 별도 baseline artifact로
저장한다. 그 후 Phase 2 이후 작업은 각 단계마다 변경 예정 파일을 먼저 보고하고,
관련 테스트 → 전체 회귀 테스트 → rollback 확인 순서로 수행한다.

운영 pgvector/MinIO credential이나 외부 통합 플래그가 준비되지 않은 상태에서는
해당 항목을 완료로 표시하지 않고 운영 설정 대기로 유지한다.
