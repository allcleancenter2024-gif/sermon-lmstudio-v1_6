# Phase 1C-3 Doctrine Repository 완료 보고

## 작업 전 Baseline

- Git status/branch: 현재 작업 디렉터리는 Git 저장소가 아니어서 확인할 수 없음 (`fatal: not a git repository`).
- 제품 버전 표기: export manifest의 `sermon-lmstudio-final-package-v40`.
- 전체 pytest Baseline: `212 passed`, failed/error `0`.
- 이번 요청 확인 시 Doctrine Repository 구현은 이미 작업 트리에 존재했으며, 이번 실행에서는 Doctrine 소스 로직을 재수정하지 않았다.

## Doctrine 기존 구조

기존 Core public 경로는 유지되며 구현은 다음처럼 분리되어 있다.

```text
app.main → app.core compatibility import
app.core → app.repositories.doctrine → SQLite
```

`build_doctrine_index`와 `doctrine_search`의 Provider 호출, vector packing/scoring, 전통(tradition) 선택 정책은 Core에 남아 있다.

## Doctrine 의존 관계

| 함수 | 현재 파일 | DB/table | 호출·관계 |
|---|---|---|---|
|`add_doctrine_chunk`|`app.repositories.doctrine` (core re-export)|`doctrine_chunks`|`POST /api/doctrine`; 입력 검증은 main, insert는 Repository|
|`fetch_doctrine_chunks`|Repository|`doctrine_chunks`|`build_doctrine_index` raw 입력|
|`persist_doctrine_embeddings`|Repository|`doctrine_embeddings`|`build_doctrine_index`가 Provider/packing 후 호출|
|`fetch_doctrine_vector_rows`|Repository|`doctrine_embeddings JOIN doctrine_chunks`|`doctrine_search`가 Provider query 후 호출|
|`build_doctrine_index`|`app.core`|간접적으로 위 두 table|Provider embedding·batch·packing orchestration|
|`doctrine_search`|`app.core`|간접적으로 위 두 table|Provider query·tradition 필터·scoring|

Doctrine rows는 `build_research_packet`의 `doctrine_sources`로 전달되고, `doctrine_alignment`/`doctrine_ready` 및 prompt grounding에 사용된다. Repository는 이 비즈니스 로직을 호출하지 않는다.

## 이동한 함수

- `add_doctrine_chunk`
- `fetch_doctrine_chunks`
- `persist_doctrine_embeddings`
- `fetch_doctrine_vector_rows`
- 위 함수들이 사용하는 Doctrine table bootstrap

## core.py에 남긴 Compatibility Interface

`app.core`는 위 Repository 함수를 같은 이름으로 import/re-export한다. `app.main`과 기존 테스트의 import/patch 경로를 변경하지 않았으며, `build_doctrine_index`·`doctrine_search` public signature도 유지한다.

## 새 Repository 구조

`app/repositories/doctrine.py`는 SQLite connection/table bootstrap, Doctrine chunk CRUD/read, precomputed embedding batch upsert, vector row read만 담당한다. `app.core`, `app.main`, Provider, RAG service, Sermon generator를 import하지 않는다.

## 변경 파일

- `app/repositories/doctrine.py`
- `app/core.py` (Doctrine import/re-export 및 호출 위임)
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE1C_DOCTRINE_REPOSITORY_REPORT.md`

## SQLite Schema 영향

없음. 기존 `doctrine_chunks`와 `doctrine_embeddings` table/column/UNIQUE 정의를 그대로 사용하며 migration, rename, type 변경, 데이터 재작성은 수행하지 않았다.

## API 영향

없음. `/api/doctrine`의 URL, method, request/response shape, status/error 형식과 `/api/rag/reindex`의 응답을 변경하지 않았다. Router는 이동하지 않았다.

## Evidence Packet 영향

없음. `doctrine_search` 결과의 `tradition`, `title`, `section`, `text`, `source_url`, `license_note` 필드와 `build_research_packet`의 `doctrine_sources`/`doctrine_alignment` 결과는 유지된다. Doctrine은 Scripture/Bible evidence로 승격되지 않고 별도 doctrine evidence로 남는다.

## 순환 Import 검사

`app.repositories.doctrine` → 표준 라이브러리 + `app.paths`/SQLite만 사용한다. `core`·`main`·Provider·RAG·Sermon을 import하지 않으며, `core → repositories.doctrine` 단방향이다. 순환 import는 확인되지 않았다.

## 관련 테스트 결과

- Doctrine: `tests/test_core.py tests/test_e2e_v6.py` — `35 passed in 8.80s`
- Evidence: `tests/test_v24_research_packet.py tests/test_v25_evidence_guards.py tests/test_v27_post_generation_quality.py tests/test_v40_interpretation_flow.py` — `20 passed in 4.05s`
- Preflight: `tests/test_v26_preflight.py tests/test_v34_runtime_consistency.py` — `11 passed in 0.80s`
- Sermon regression: `tests/test_e2e_v6.py tests/test_v40_interpretation_flow.py tests/test_v40_notebooklm_bridge.py` — `13 passed in 3.32s`

## 전체 pytest 결과

`212 passed in 22.13s`, failed/error `0`.

## 발견된 문제

없음. 이번 작업 디렉터리에는 Git metadata가 없어 branch/status를 확인할 수 없었다.

## 남은 위험

- `build_doctrine_index`와 `doctrine_search`는 여전히 Provider·vector 계산·업무 정책을 Core에서 조합한다.
- Doctrine과 Evidence/Prompt의 의미적 권위 구분은 상위 Core 정책에 남아 있어 Repository만으로 보장되지 않는다. 현재 결과는 기존 정책과 동일하다.
- Repository bootstrap과 `init_db`의 table 선언이 일부 중복되지만 독립 public 호출 호환성을 위한 기존 구조다.

## Rollback 방법

1. `app/core.py`의 기존 Doctrine DB 구현과 import를 복원한다.
2. `app/repositories/doctrine.py`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md` 및 본 보고서를 이전 상태로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB 자체는 수정하지 않았으므로 데이터 rollback은 필요하지 않다.

## 다음 권장 단계

지시서에 따라 Doctrine Repository 결과만 보고하고 자동 진행을 중단한다. Bible·Sermon·RAG·Grounding·Router·DB migration은 별도 분석과 승인 없이는 시작하지 않는다.
