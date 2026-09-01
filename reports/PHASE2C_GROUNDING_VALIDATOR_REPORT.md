# Phase 2C Grounding Validator 완료 보고

## 작업 전 Baseline

Git metadata가 없는 작업 디렉터리이며 제품 버전 후보는 `sermon-lmstudio-final-package-v40`이다. Legacy lexical/weighted fusion이 기본이고 FTS5·RRF는 선택 전략이다. 전체 기준선은 **212 passed** (`22.02s`)였다.

## 기존 Evidence 구조

`build_research_packet()`이 `bible_sources`, `original_notes`, `doctrine_sources`를 dict 목록으로 조립하고 기존 `build_grounding()`이 성경 passage dict를 Prompt용 문자열로 변환한다.

## 새 Evidence 모델

`app.evidence.models.EvidenceCandidate` dataclass를 추가했다. source identity, source type/name, reference, text, page/chunk, retrieval rank/score, 원본 metadata를 보존하며 `as_dict()`로 backward-compatible mapping을 제공한다.

## Source Type Mapping

`scripture`, `original_language`, `translation`, `doctrine`, `commentary`, `user_material`, `notebook`, `web`, `unknown`을 지원한다. 기존 translation+reference dict는 scripture로 adapter되고 lemma/morphology는 original_language로 추론한다.

## Grounding Tier 정책

Tier A: scripture/original_language, Tier B: translation/doctrine, Tier C: commentary/user_material/notebook, Tier D: web, Tier X: unknown 또는 검증 불가 source.

## Approved / Weak / Rejected 규칙

등록 Scripture는 reference·본문·번역본을 확인하면 A/approved, 미등록이면 X/rejected다. Original language는 reference와 lemma/morphology가 필요하다. Translation/Doctrine은 출처와 본문이 있으면 B/approved, metadata가 부족하면 B/weak다. Notebook/User/Commentary는 C/weak(normal) 또는 strict에서 rejected이며, Unknown은 X/rejected다.

## Grounding Validator 구조

`app.grounding.validator.validate_evidence(candidate, context)`가 순수 규칙 기반으로 `GroundingDecision`을 반환한다. `filter_evidence()`는 approved와 normal 모드의 weak만 유지하고 rejected를 제외한다. LLM, embedding, HTTP 호출은 없다.

## 변경 파일

- `app/evidence/__init__.py`
- `app/evidence/models.py`
- `app/evidence/normalize.py`
- `app/grounding/__init__.py`
- `app/grounding/models.py`
- `app/grounding/validator.py`
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE2C_GROUNDING_VALIDATOR_REPORT.md`

## Feature Flag

`GROUNDING_VALIDATOR_ENABLED`를 제공하며 기본값은 `false`다. 기본 비활성 상태에서는 기존 Evidence/Prompt 흐름이 변하지 않는다.

## Strictness 정책

`GroundingContext.strictness`는 `normal`(weak 허용)과 `strict`(approved만 허용)를 지원한다. UI 노출이나 새 설정 화면은 추가하지 않았다.

## build_grounding 영향

기존 `build_grounding()` 구현과 호출부를 변경하지 않았다. Validator는 앞단 adapter/filter로 독립 제공된다.

## Preflight 영향

Preflight 규칙 및 response contract 변경 없음. 별도 통합 없이 optional runtime 계층으로 제공한다.

## RAG 영향

RAG semantic/lexical/FTS5/RRF 알고리즘과 score는 변경하지 않았다. 검색 score로 Grounding tier를 결정하지 않는다.

## RRF 영향

RRF rank/score 계산과 identity 처리는 변경하지 않았다. 정규화 모델은 `semantic_rank`, `lexical_rank`, `rrf_score`를 metadata로 보존한다.

## FTS5 영향

FTS5 전략 및 fallback 변경 없음.

## LM Studio 영향

Validator는 LM Studio endpoint나 Provider를 호출하지 않는다.

## DB 영향

SQLite schema, 데이터, migration 변경 없음. Scripture 등록 확인은 기존 Bible Repository의 `compare_reference()`를 사용한다.

## API 영향

URL, method, request/response, status/error 형식 변경 없음. 새 모델은 내부 adapter로만 사용 가능하다.

## 성능 영향

후보별 단순 metadata 검사와 필요한 reference lookup만 수행한다. embedding/LLM/DB 전체 scan은 없다.

## 관련 테스트 결과

Evidence/Validator 기본 동작 및 기존 RAG·Generation·Preflight·Backup 회귀: **59 passed in 13.34s**.

## 전체 pytest 결과

**212 passed in 22.12s**, failed 0, error 0.

## 발견된 문제

없음. Git status/branch는 repository metadata 부재로 확인할 수 없다. Validator enabled 상태의 API 통합은 기본 비활성 보존을 위해 별도 연결하지 않았다.

## 남은 위험

현재 source metadata가 불완전한 기존 dict는 unknown/weak로 분류될 수 있다. Notebook/Web 자료의 실제 adapter와 Evidence Packet 통합은 후속 단계에서 별도 검토가 필요하다. 기존 build_grounding과 자동 연결하지 않았으므로 enabled flag만으로 API 결과가 바뀌지는 않는다.

## Rollback 방법

`GROUNDING_VALIDATOR_ENABLED=false`를 유지하고 새 evidence/grounding import를 제거하면 된다. 기존 `build_grounding()`과 RAG/Prompt/DB 데이터는 그대로 남아 rollback 데이터 작업이 필요 없다.

## 다음 권장 단계

이번 Phase 2C 범위에서 중단한다. Validator 기본 활성화, Grounding Audit, Web Grounding, Prompt/Router/UI 변경은 별도 승인 후 진행한다.
