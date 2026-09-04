# 성경 근거 설교 작성기 구조 개선 권장 작업지시서

**작성일:** 2026-09-04  
**기준 문서:** `C:\Users\Home_care\Downloads\SERMON_ARCHITECTURE_3_OPTIONS_2026.md`  
**현재 기준 버전:** V40.9.10  
**적용 원칙:** 현재 버전 흐름 유지, 기존 기능 보존, 단계별 변경, 승인 후 구현

**버전 정책 추가:** 구조 변경의 범위와 외부 계약 영향에 따라 버전을 결정한다. 내부 호환 Facade·테스트 정리처럼 사용자 계약을 유지하는 변경은 현재 버전을 유지하고, API·DB·배포 계약이 바뀌는 경우에만 패치/마이너 버전업을 별도 검토한다.

## 1. 목적과 적용 범위

이 작업지시서는 현재 정상 운영 중인 LM Studio 기반 성경 근거 설교 작성기를 기준으로, 구조를 문서의 제2안인 **계층형 모듈러 모놀리스** 방향으로 점진적으로 정리하기 위한 실행 기준이다.

이번 작업지시서에서는 V60으로 버전을 점프하지 않는다. 현재 제품의 버전 흐름과 호환성을 유지하면서 기능 단위로 변경한다. PostgreSQL·pgvector·MinIO의 즉시 전환도 수행하지 않는다.

## 2. 문서 분석 결론

원문은 세 가지 구조를 제시한다.

| 대안 | 평가 | 적용 판단 |
|---|---|---|
| 제1안 통합 워크벤치 | 빠른 MVP와 단순한 설치에 유리하지만 장기 결합도가 높아짐 | 현재 기능의 현상 유지 기준으로만 활용 |
| 제2안 계층형 모듈러 모놀리스 | 1인 개발, Windows 로컬 운영, 단계적 확장에 적합 | **권장 적용안** |
| 제3안 도메인 이벤트·파이프라인 | 대규모 동시 처리와 장애 격리에 유리하지만 운영 복잡도가 큼 | 향후 병목 모듈 추출 시 검토 |

문서의 핵심 원칙은 성경 근거 우선, 교단·청중 프로필 분리, 출처 추적, 근거 부족 시 생성 차단, 목회자 승인, 저작권·checksum 보존이다. 현재 프로그램의 Evidence, Grounding, Review, Lock, Audit, RAG 경계와 방향이 맞는다.

## 3. Phase 0 — 변경 없는 구조 감사 결과

### 3.1 기준선 저장

- 브랜치: `main`
- 현재 버전: `V40.9.10`
- 기준 커밋: `168223b3f10a21f62311e93a294ac247df21e850`
- 원격 `origin/main`: 기준 커밋과 동일
- 추적 파일 변경: 없음
- 운영 데이터: `data/`, `backups/`, `exports/`, `fonts/`의 비추적 파일은 보존하고 변경하지 않음

현재 정상 소스 기준선은 Git 커밋으로 저장되어 있다. 운영 DB와 비추적 자료는 커밋에 포함되지 않으므로 별도 백업이 필요할 경우 구현 전 별도 승인을 받는다.

### 3.2 테스트 기준선

프로젝트 `.venv`에서 전체 테스트를 실행한 결과:

```text
363 passed, 11 skipped in 100.31s
```

Skip은 PostgreSQL, MinIO, schema drift, readiness 등 명시적 외부 통합 환경이 없는 테스트다. 현재 코드 실패는 확인되지 않았다.

### 3.3 현재 구조

```text
app/
├─ main.py / core.py
├─ routers/
├─ repositories/
├─ services/
├─ providers/
├─ rag/                 # Semantic + FTS5 + Hybrid/RRF
├─ evidence/ / grounding/
├─ formatting/ / exporters/
└─ 원어·교리·저장소 모듈
```

현재 프로그램은 이미 라우터, 저장소, Provider, RAG, Evidence, 출력 계층을 부분적으로 분리하고 있다. 따라서 문서의 `app/modules/` 구조로 파일을 일괄 이동하는 것보다 기존 import 경로를 보존하는 내부 경계 강화가 안전하다.

## 4. 충돌 감사

| 영역 | 현재 상태 | 즉시 변경 시 위험 | 권장 해결 |
|---|---|---|---|
| 버전 | 여러 실행·UI·검증 지점이 V40.9.10을 사용 | 일부 파일만 변경하면 launcher와 UI 버전 불일치 | 중앙 버전 공급원과 계약 테스트를 먼저 정리 |
| DB | SQLite가 기본이고 PostgreSQL Adapter가 선택형 | 즉시 전환 시 데이터·백업·마이그레이션 위험 | SQLite 유지, Adapter 계약 검증 후 단계 전환 |
| RAG | Semantic, FTS5, Hybrid/RRF, Doctrine RAG 공존 | 인덱스·임베딩·검색 결과 이중화 | 기존 RAG를 기본값으로 유지하고 동일 질문 회귀 비교 |
| 모듈 경로 | `app.core`, `app.main`, `app.repositories.*` 사용 | 일괄 이동 시 기존 테스트와 import 파괴 | 호환 Facade와 점진적 내부 추출 |
| DB 엔터티 | sermon, project, review, audit, doctrine 테이블이 이미 존재 | 문서 엔터티를 중복 생성할 위험 | 기존 Repository·테이블 매핑 후 필요한 필드만 migration |
| Provider | LM Studio localhost 경계가 보호됨 | 원격 주소 허용 또는 장애 전파 위험 | `127.0.0.1` 기본값과 기능 단위 오류 유지 |
| 원어·근거 | 성경·원어·교리 자료와 출처 metadata 보존 | 새 자료 계층이 확정 근거로 잘못 승격될 위험 | Source of Truth와 provenance 유지 |
| 출력·승인 | 검토·승인·잠금 후 출력 구조 존재 | 새 생성 흐름이 승인 게이트 우회 가능 | 모든 새 경로를 기존 review/lock/audit에 연결 |

### 판정

```text
구조적 문제: 전면 일괄 전환, 즉시 DB 교체, 기존 경로 삭제, RAG 이중 기본화
적용 가능: 현재 버전 흐름을 유지하는 호환형 계층 모듈화
Phase 0 판정: 통과
```

## 5. 권장 목표 구조

문서의 제2안을 현재 코드에 맞게 다음 순서로 구현한다.

```text
기존 FastAPI 진입점
    ↓
호환 Router / Application Facade
    ↓
도메인 경계
    ├─ scripture      성경·본문·원어
    ├─ evidence       근거·출처·스냅샷
    ├─ profiles       교단·청중·설교형식
    ├─ sermons        프로젝트·버전·생성
    ├─ reviews        품질·검토·승인·잠금
    ├─ providers      LM Studio 및 선택 Provider
    ├─ library        자료·보존·저작권
    └─ exports        승인본 출력
    ↓
기존 SQLite / 선택형 Adapter / MinIO 경계
```

핵심은 새 폴더 이름보다 경계와 계약을 먼저 고정하는 것이다.

## 6. 단계별 작업지시

### Phase 1 — 버전 흐름 및 호환성 계약 고정

1. `VERSION.txt`, `app.main`, launcher, start script, health/project API, UI 표시의 버전 공급원을 조사한다.
2. 현재 버전 흐름을 유지한 채 중복 상수의 변경 지점을 하나씩 정리한다.
3. API 응답 버전, launcher 버전 비교, UI 버전 표시를 계약 테스트로 고정한다.
4. V40.9.10 기존 백업과 복원 동작을 유지한다.

**완료 조건:** 버전 표시와 실행 검증이 모두 동일하고 전체 테스트가 기준선 이상이다.

### Phase 2 — Application Facade와 도메인 경계

1. 기존 `app.core`와 `app.main`의 외부 import를 보존한다.
2. scripture, evidence, profiles, sermons, reviews 경계를 작은 Facade부터 만든다.
3. Router가 SQLite SQL을 직접 호출하지 않도록 기존 Repository 계약을 사용한다.
4. 한 번에 `core.py`나 `main.py` 전체를 재작성하지 않는다.

**완료 조건:** 기존 API와 테스트가 유지되고 새 경계 계약 테스트가 추가된다.

### Phase 3 — 교단·청중·설교형식 프로필

1. 기존 doctrine 구조와 중복되지 않는 Profile 읽기 모델을 먼저 설계한다.
2. 교단 프로필과 청중 프로필을 독립적으로 관리한다.
3. 프로필은 버전, 적용일, 출처, 승인자를 기록한다.
4. 논쟁 교리는 공통 견해·교단 견해·다른 견해·불확실성으로 표시한다.

**완료 조건:** 프로필이 설교문에 직접 확정 문장으로 주입되지 않고 검증 규칙으로 작동한다.

### Phase 4 — 근거 스냅샷·주장·검토 연결

1. 기존 Evidence Packet과 Audit metadata를 우선 재사용한다.
2. 생성 실행 시 본문·원어·교리 근거의 snapshot 식별자를 기록한다.
3. 설교 주장과 source ID 연결을 검증한다.
4. 근거 부족·인용 누락·교리 충돌은 초안 상태에서 경고하거나 차단한다.

### Phase 5 — 저장소와 RAG 확장 검토

1. SQLite Semantic/FTS5/Hybrid 결과를 기준선으로 고정한다.
2. 동일 질문 세트로 새 검색 결과를 비교한다.
3. 기존 결과보다 명백히 나빠지면 새 방식을 기본값으로 전환하지 않는다.
4. PostgreSQL·pgvector·MinIO는 별도 Adapter와 통합 테스트를 통과한 뒤 선택적으로 활성화한다.

### Phase 6 — 비동기 작업과 운영 고도화

작업 큐나 제3안의 Worker 분리는 생성·OCR·색인·출력 병목이 실제로 확인된 뒤 검토한다. 현재 단계에서 분산 시스템을 먼저 도입하지 않는다.

## 7. 변경 예정 파일 범위

실제 구현 전 다시 확정하며, Phase 0에서는 파일을 변경하지 않는다.

예상 범위:

- `app/config.py`, `app/constants.py`
- `app/main.py`, `app/core.py` — 호환 Facade 중심의 최소 변경
- `app/routers/`, `app/repositories/`, `app/services/`
- `app/providers/`, `app/rag/`, `app/evidence/`, `app/grounding/`
- 필요한 경우에만 `app/migrations.py`와 신규 migration
- 관련 `tests/`
- 단계 완료 후에만 `VERSION.txt`, `start.bat`, `verify_version.py`, UI 버전 표시 파일
- 구현 문서와 rollback 문서

변경 금지 원칙:

- `data/bible.db` 직접 수정 금지
- 기존 테이블 삭제 금지
- 기존 RAG 삭제 금지
- 승인되지 않은 source 자료 삭제 금지
- `0.0.0.0`로 LM Studio 공개 금지

## 8. 승인 게이트

다음 단계로 넘어가기 전 아래를 확인한다.

1. 변경 예정 파일과 migration SQL을 사전 보고한다.
2. DB 변경 시 백업·upgrade·downgrade·upgrade를 검증한다.
3. 기존 일반 RAG 회귀 질문 세트를 실행한다.
4. 전체 테스트가 `363 passed, 11 skipped` 이상인지 확인한다.
5. 실패 시 추가 변경을 중단하고 원인·영향·rollback을 보고한다.
6. 사용자가 승인한 경우에만 다음 Phase를 구현한다.

## 9. 롤백 계획

- 코드: 기준 커밋 `168223b`로 복귀하는 별도 복구 절차 사용
- DB: 변경 전 백업을 만든 뒤 migration downgrade 실행
- RAG: 새 검색 전략은 feature flag로 비활성화하고 기존 전략으로 복귀
- Provider: LM Studio 기본 Provider와 localhost 주소 유지
- UI: 새 화면은 기존 경로의 fallback을 보존
- 운영 데이터: `data/`, `backups/`, `exports/`, `fonts/`는 삭제하지 않음

## 10. 다음 진행 결정

Phase 0은 통과했지만 구현은 아직 시작하지 않았다. 다음 권장 단계는 **Phase 1 버전·호환성 계약 고정 설계 보고**이다.

사용자 승인 전에는 소스코드, DB schema, 제품 버전, RAG 기본 동작을 변경하지 않는다.

## 경고

- 이 문서는 구조 개선 작업지시서이며 교리적 판단이나 성경 본문 해석을 대신하지 않는다.
- 문서의 PostgreSQL·pgvector·MinIO 목표는 장기 선택지이지 현재 즉시 전환 명령이 아니다.
- 외부 통합 Skip 테스트는 실제 인프라가 준비되기 전까지 전체 성공으로 간주하지 않는다.
