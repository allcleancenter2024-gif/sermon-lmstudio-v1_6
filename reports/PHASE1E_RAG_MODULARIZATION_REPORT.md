# Phase 1E RAG 모듈화 완료 보고

## 작업 전 Baseline

Git metadata가 없는 작업 디렉터리이며 제품 버전 후보는 `sermon-lmstudio-final-package-v40`이다. 전체 pytest 기준선은 **212 passed**, failed/error 0 (`21.89s`)이다.

## 기존 RAG 구조

`core.py`가 `semantic_search`와 `hybrid_search`의 orchestration을 보유했고, cosine/vector 복원 helper는 이미 `app/rag/semantic.py`, fusion helper는 `app/rag/hybrid.py`에 있었다. RAG DB 읽기/쓰기는 `app/repositories/rag.py`, lexical 검색은 `app/repositories/bible.py`에 있었다.

## RAG Dependency Map

|책임|현재 모듈|DB|Provider|Evidence/Grounding|
|---|---|---|---|---|
|Embedding 생성|`core.build_rag_index`|Repository 저장|`client.embeddings`|간접|
|Embedding 저장/조회|`repositories.rag`|SQLite|없음|없음|
|Semantic Search|`rag.semantic`|`fetch_rag_vector_rows`|`client.embeddings`|후속 후보|
|Lexical Search|`repositories.bible.search_passages`|SQLite LIKE|없음|후속 후보|
|Hybrid Fusion|`rag.hybrid`|간접|간접|후속 후보|

## 기존 검색 알고리즘

Semantic Search는 저장 vector 전체를 읽어 cosine similarity를 계산하고 내림차순으로 `limit`개를 반환한다. Lexical Search는 기존 reference/text `LIKE` 검색과 reference/translation 정렬을 그대로 사용한다.

## 기존 Hybrid 계산식

Semantic 점수는 `0.75 * max(semantic_score, 0)`, lexical rank 점수는 `0.25 * (1 - rank / max(len(lexical), 1))`이며 id별 합산 후 점수 내림차순으로 제한한다. 계산식 변경 없음.

## 이동한 함수

- `semantic_search` → `app.rag.semantic.semantic_search`
- `hybrid_search` → `app.rag.hybrid.hybrid_search`

## 이동하지 않은 함수

`build_rag_index`, embedding packing, embedding persistence, lexical SQL, `recommend_related`, Evidence Packet/ Grounding/Prompt/Provider/Router는 이번 단계에서 이동하지 않았다.

## 새 RAG 모듈 구조

```text
app/rag/semantic.py   # vector restore, cosine, semantic_search
app/rag/hybrid.py     # weighted fusion, hybrid_search
app/repositories/rag.py   # vector DB read/write
app/repositories/bible.py # lexical LIKE search
```

## core.py Compatibility Wrapper

기존 `core.semantic_search(...)`, `core.hybrid_search(...)` public 함수는 유지하며 각각 새 RAG 모듈을 호출한다. 기존 호출부와 API endpoint는 변경하지 않았다.

## 변경 파일

- `app/rag/semantic.py`
- `app/rag/hybrid.py`
- `app/core.py`
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE1E_RAG_MODULARIZATION_REPORT.md`

## DB 영향

SQLite schema와 데이터 변경 없음. 기존 Repository SQL과 vector serialization을 그대로 사용한다.

## Embedding 영향

embedding model, endpoint, dimension, binary/JSON 복원, normalization을 변경하지 않았다. Embedding 생성/저장은 기존 `build_rag_index` 경로 그대로다.

## Semantic Search 결과 비교

동일한 vector rows, query embedding, cosine 계산, 내림차순 정렬, limit을 사용한다. 관련 회귀 테스트 통과로 결과 구조와 순서 보존을 확인했다.

## Lexical Search 결과 비교

Lexical SQL은 이동하지 않고 기존 `search_passages`를 그대로 호출한다. LIKE 조건, 정렬, limit 변경 없음.

## Hybrid Search 결과 비교

기존 semantic/lexical 입력과 `fuse_hybrid_results` weighted merge를 동일하게 사용한다. 관련 회귀 테스트 통과.

## Evidence 영향

RAG 결과를 Evidence Packet으로 변환하는 로직은 변경하지 않았다.

## Grounding 영향

Grounding 정책과 판정은 변경하지 않았다. RAG는 후보 검색만 담당한다.

## Sermon Service 영향

Sermon Service API와 workflow는 변경하지 않았다. 기존 core compatibility wrapper를 통해 동일한 RAG 결과를 받는다.

## API 영향

URL, method, request/response, status/error 형식 변경 없음.

## LM Studio 호출 횟수 비교

Semantic Search당 query embedding 1회, 기존 generation/embedding 호출 경로를 유지하며 중복 호출을 추가하지 않았다.

## 성능 비교

전체 vector scan, Python cosine, lexical LIKE 및 weighted merge를 그대로 유지했다. 알고리즘 최적화나 성능 개선은 수행하지 않았다.

## 순환 Import 검사

`app.rag` 모듈은 `app.core`, `app.main`, Sermon Service, Grounding, Router를 import하지 않는다. Repository와 표준 helper만 사용하며 compile/import 검사 통과.

## 관련 테스트 결과

RAG·Evidence·Preflight·Generation 회귀: **60 passed in 12.76s**.

## 전체 pytest 결과

**212 passed in 22.14s**, failed 0, error 0.

## 추가 테스트

별도 테스트 파일은 추가하지 않았다. 기존 RAG 및 생성 회귀 세트를 사용했다.

## 발견된 문제

없음. Git status/branch는 저장소 metadata 부재로 확인 불가.

## 남은 위험

Embedding 생성과 `build_rag_index`는 아직 `core.py`에 남아 있다. Lexical SQL은 Bible Repository가 소유한다. 후속 이동 시 결과 snapshot과 호출 횟수 비교를 별도로 유지해야 한다.

## Rollback 방법

`core.py` wrapper 내부를 기존 inline semantic/hybrid 구현으로 복원하고 RAG 모듈의 새 함수 및 import를 제거하면 된다. DB schema/data에는 변경이 없어 데이터 rollback은 필요 없다.

## 다음 권장 단계

이번 Phase 1E 범위에서 중단한다. FTS5, RRF, Grounding Validator, Prompt 분리, Router 분리는 별도 승인 후 진행한다.
