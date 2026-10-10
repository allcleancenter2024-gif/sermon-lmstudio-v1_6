# Gate 1 Research Package Schema Design

## 1. 목적

현재 7단계 설교 Workflow, SQLite, Evidence/Audit, 목회자 승인, 최종 잠금 및 출력 경로를 교체하지 않고 Research Package, Language Package, Evidence Packet, Output Profile을 추가하기 위한 비영속 설계 기준을 고정한다.

이 문서는 Schema 승인용 설계이며 운영 DB migration을 실행하지 않는다.

## 2. 설계 원칙

1. `sermons`와 `sermon_versions`는 설교 및 설교 버전의 정본으로 유지한다.
2. Research/Language 결과는 독립 Section 버전으로 저장한다.
3. Package는 Section을 조합한 읽기 모델이며 Section 내용을 중복 저장하지 않는다.
4. Claim과 Evidence 연결은 기존 `generation_audits.evidence_json`을 즉시 제거하지 않고 adapter로 병행한다.
5. 프로젝트 최종 승인은 기존 `sermon_reviews`와 `sermon_version_locks`를 통과해야 한다.
6. 최종 잠금 이후 Section을 덮어쓰지 않는다. 수정은 새 Section 버전으로 만든다.
7. Renderer는 연구 데이터를 생성하지 않고 승인된 Snapshot만 표현한다.
8. SQLite를 기본값으로 유지하고 PostgreSQL, pgvector, MinIO 활성화와 결합하지 않는다.

## 3. 기존 데이터 매핑

| 신규 개념 | 기존 데이터 또는 서비스 | 융합 방식 |
|---|---|---|
| Sermon Brief | `SermonRequest`, `sermon_versions.metadata_json`, `sermon_project_meta` | 기존 필드를 adapter로 조합 |
| Passage Structure | `build_passage_study`, 성경 본문 repository | `structure` Builder 입력 |
| Language Package | 번역 비교, original notes, morphology, alignment, apparatus | 기존 서비스 결과를 표준 payload로 변환 |
| Evidence Packet | generation evidence trace, `generation_audits.evidence_json` | 기존 trace를 Claim/Source adapter로 변환 |
| Human Approval | `sermon_reviews` | 프로젝트 승인 정본으로 유지 |
| Publication Lock | `sermon_version_locks` | Snapshot ID를 잠금 metadata에 연결하는 후속 migration 검토 |
| Output Profile | formatting registry, exporters | 기존 Renderer 선택 정책으로 사용 |
| Research Book | formatting `Document`와 format router | 전용 document adapter 추가 |

## 4. 제안 테이블

### 4.1 `sermon_research_packages`

Section 버전 묶음의 논리적 Package를 나타낸다. 본문 전체를 중복 저장하지 않고 선택된 Section 버전과 상태를 참조한다.

| 필드 | 역할 |
|---|---|
| `id` | Package 식별자 |
| `project_id` | 기존 `sermons.id` 참조 |
| `package_type` | `research` 또는 `language` |
| `version` | 프로젝트·유형 내 증가 버전 |
| `status` | Package 조합 상태 |
| `section_versions_json` | Section ID와 버전 매핑 |
| `created_at` | 생성 시각 |

### 4.2 `sermon_sections`

Canary의 핵심 정본이다.

| 필드 | 역할 |
|---|---|
| `id` | Section 레코드 식별자 |
| `project_id` | 기존 설교 프로젝트 식별자 |
| `section_type` | Registry ID |
| `version` | 프로젝트·Section별 증가 버전 |
| `status` | 생성 상태 |
| `content_json` | Builder의 구조화된 결과 |
| `source_coverage` | `0.0`~`1.0` 근거 연결 비율 |
| `quality_status` | 품질 검사 상태 |
| `review_status` | Section 검토 상태 |
| `source_snapshot_id` | Builder 입력 근거 Snapshot |
| `created_at` | 생성 시각 |
| `updated_at` | 상태 변경 시각 |

권장 유일성 제약은 `(project_id, section_type, version)`이다. 기존 버전을 update로 덮어쓰지 않는다.

### 4.3 `sermon_claims`

| 필드 | 역할 |
|---|---|
| `id` | 안정적인 Claim ID |
| `project_id` | 프로젝트 식별자 |
| `section_id` | Claim을 만든 Section 버전 |
| `statement` | 검증 대상 주장 |
| `claim_type` | 본문·원어·역사·학술·적용 등의 유형 |
| `viewpoint` | 특정 학자·전통의 견해 표시 |
| `confidence` | `0.0`~`1.0` |
| `verification_status` | Evidence Packet 상태 |
| `created_at` | 생성 시각 |

### 4.4 `sermon_evidence_links`

Claim과 기존 또는 신규 Source metadata의 다대다 연결이다. Source 본문을 복제하지 않고 안정적인 Source 식별자와 인용 위치를 저장한다.

### 4.5 `sermon_assets`

지도·성화 등 출력 자산의 source, license, attribution, checksum을 저장한다. 출처 또는 사용 조건이 없는 자산은 승인 상태가 될 수 없다.

### 4.6 `sermon_render_snapshots`

연구·원어·설교·Evidence·Section·Renderer·Output Profile 버전을 고정한다. 동일 Snapshot의 입력 식별자는 변경할 수 없다.

### 4.7 `sermon_review_events`

Section 수준 검토 이력만 기록한다. 프로젝트 최종 승인 정본은 기존 `sermon_reviews`를 유지한다.

## 5. 상태 전이

```text
not_generated
    ↓
generating
    ├─→ failed
    ├─→ insufficient_evidence
    └─→ ready
             ↓
        needs_review
             ↓
          approved
```

- `failed`와 `insufficient_evidence`는 해당 Section만 재시도한다.
- 재생성은 기존 레코드를 덮어쓰지 않고 다음 버전을 생성한다.
- `approved`는 비어 있는 content와 함께 저장할 수 없다.
- Section 승인만으로 설교 최종 잠금이 가능해지지 않는다.
- 최종 잠금은 기존 Audit 및 목회자 승인 조건을 모두 만족해야 한다.

## 6. Snapshot 규칙

Snapshot은 최소 다음 식별자를 포함한다.

```yaml
project_id: 7
research_version: 2
language_version: 3
sermon_version: 4
evidence_version: 5
renderer_version: page-format-v2
section_versions:
  structure: 2
  original_language_keywords: 1
output_profile:
  enabled_formats:
    - html
    - markdown
created_at: 2026-10-02T12:00:00+09:00
```

동일 Snapshot을 다시 출력할 때 생성 모델이나 RAG를 다시 호출하지 않는다. 저장된 승인 결과와 고정된 Renderer 버전만 사용한다.

## 7. Canary API 초안

기존 `main.py`에 직접 추가하지 않고 후속 Gate에서 `app/routers/research.py` 경계를 사용한다.

| Method | 경로 | 역할 |
|---|---|---|
| GET | `/api/projects/{project_id}/research/sections` | Section 상태와 최신 버전 조회 |
| GET | `/api/projects/{project_id}/research/sections/{section_id}` | 선택 Section 버전 조회 |
| POST | `/api/projects/{project_id}/research/sections/{section_id}/generate` | 한 Section 생성 |
| POST | `/api/projects/{project_id}/research/sections/{section_id}/retry` | 실패 Section 새 버전 재시도 |
| GET | `/api/projects/{project_id}/research/evidence-coverage` | 근거 coverage 조회 |
| POST | `/api/projects/{project_id}/research/snapshots` | 승인된 버전으로 출력 Snapshot 생성 |

## 8. Migration 계획

후속 Gate에서 다음 순서를 적용한다.

1. 기존 `data/bible.db` 백업 생성
2. 신규 migration ID 및 idempotent DDL 작성
3. 빈 DB migration test
4. 기존 데이터가 있는 DB migration test
5. migration 재실행 test
6. 기존 테이블 row count 및 핵심 checksum 비교
7. 전체 회귀 테스트
8. 명시적 승인 후 운영 DB 적용

## 9. Rollback 계획

- Canary 기본값은 OFF로 시작한다.
- Router와 UI는 feature flag로 비활성화할 수 있어야 한다.
- 신규 테이블은 기존 생성·저장·승인·출력 경로의 필수 의존성이 되지 않는다.
- 운영 rollback은 application flag OFF와 migration 전 DB 백업 복원을 기본으로 한다.
- 기존 테이블 또는 컬럼을 삭제하거나 이름을 변경하지 않는다.

## 10. 품질 Gate

- Section 계약 validation 통과
- Evidence source/citation/license coverage 유지
- Greek/Hebrew Unicode 원문 보존
- HTML 출력 시 untrusted content escape
- 승인되지 않은 Section의 최종 Snapshot 포함 차단
- Snapshot의 Section ID 중복 차단
- 기존 7단계 Workflow 계약 테스트 통과
- 전체 테스트 기준선 이상 유지

## 11. 경고

- 이 설계는 아직 운영 DB에 적용되지 않았다.
- 현재 계약 모듈은 migration이나 HTTP endpoint를 생성하지 않는다.
- 외부 자료의 citation, license, attribution을 확인하지 않고 `approved`로 전환해서는 안 된다.
- Snapshot 생성 시 기존 목회자 승인과 최종 잠금 조건을 우회해서는 안 된다.

## 12. Gate 2 진입 조건

- Gate 1 계약 테스트 통과
- 전체 회귀 테스트가 기준선보다 나빠지지 않음
- 운영 DB가 변경되지 않았음을 확인
- Canary 첫 구현을 `structure` 한 Section으로 제한
- 기존 Provider, RAG, Repository, Renderer를 adapter로 재사용
