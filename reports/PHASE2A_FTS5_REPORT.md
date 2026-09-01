# Phase 2A SQLite FTS5 완료 보고

## 작업 전 Baseline

Git metadata가 없는 작업 디렉터리이며 제품 버전 후보는 `sermon-lmstudio-final-package-v40`이다. 전체 pytest 기준선은 **212 passed**, failed/error 0 (`22.05s`)이다.

## SQLite Version

Python `3.14.6`, sqlite3 runtime `3.50.4`.

## FTS5 지원 여부

지원됨. 임시 DB에서 `CREATE VIRTUAL TABLE ... USING fts5` 생성/삭제 검사를 통과했다.

## 기존 Lexical Search 구조

`app.repositories.bible.search_passages()`가 reference/text에 대한 기존 LIKE 검색과 `ORDER BY reference, translation`을 수행한다. 이 경로는 삭제하거나 변경하지 않았다.

## 새 FTS5 구조

`app.rag.fts`에 FTS5 지원 검사, 파생 index 생성/rebuild, 검색 및 fallback을 추가했다. `app.rag.hybrid.hybrid_search(strategy="fts5")`로 선택 가능하다.

## FTS Table 설계

기존 테이블과 별도로 `rag_fts` virtual table을 추가했다.

```sql
CREATE VIRTUAL TABLE rag_fts USING fts5(
  source_id UNINDEXED, reference, text, source_name
)
```

`source_id`는 원본 `passages.id`, `source_name`은 기존 `translation` 값이다.

## Index 동기화 방식

검색 시 전체 rebuild하지 않는다. 관리용 `rebuild_fts_index()`가 기존 `passages`에서 파생 index를 재생성한다. 원본 데이터와 embedding은 변경하지 않는다. import/update 자동 동기화는 후속 단계 대상으로 남겼다.

## 변경 파일

- `app/rag/fts.py`
- `app/rag/hybrid.py`
- `app/core.py`
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE2A_FTS5_REPORT.md`

## Feature Flag

환경변수 `RAG_LEXICAL_STRATEGY`를 사용하며 허용값은 `legacy`, `fts5`이다. 기본값은 `legacy`다. 또한 core/hybrid public 함수에서 `strategy` 인자를 선택적으로 전달할 수 있다.

## Fallback 구조

FTS5 미지원, table/index 오류, query syntax 오류, FTS 검색 예외 시 `search_passages()` legacy LIKE 검색으로 자동 복귀한다. 직접 reference 검색 결과도 FTS 결과에 보완적으로 포함한다.

## 기존 DB Schema 영향

기존 Bible/RAG table 및 column은 변경하지 않았다. `rag_fts`만 별도 virtual table로 추가된다.

## 기존 데이터 영향

기존 `passages`를 읽어 파생 index를 생성하며 재import·embedding 재생성·원본 row rewrite가 없다. 임시 DB에서 기존 row 1건 index 구축을 확인했다.

## 한국어 검색 결과

임시 DB의 `사랑` 검색에서 FTS 결과 1건을 확인했다.

## 영문 검색 결과

기존 FTS5 tokenizer 경로를 사용하며 별도 영문 데이터가 없는 환경에서는 정량 fixture를 추가하지 않았다. legacy fallback은 동일하게 유지된다.

## Reference 검색 결과

임시 DB의 `요 3:16` 검색에서 direct reference 보완 경로를 통해 1건을 확인했다.

## Legacy vs FTS5 결과 비교

기본 전략은 legacy이므로 기존 결과와 API 동작은 동일하다. FTS5 전략은 FTS rank 결과를 `retrieval_type="fts5"`, `score` metadata로 표시하고 direct legacy reference 결과를 누락하지 않도록 병합한다.

## 검색 성능 비교

이번 단계에서는 안정성 중심으로 구현했으며 production DB에 대한 반복 latency benchmark는 수행하지 않았다. FTS5는 선택 전략이며 기본 legacy latency에는 영향이 없다.

## DB Size 변화

운영 DB에 rebuild를 실행하지 않아 실제 DB 파일 크기 변화는 0이다. FTS index는 파생 데이터이므로 rebuild 시 증가량을 별도로 측정할 수 있다.

## Hybrid Search 영향

기존 `0.75 semantic + 0.25 lexical` weighted fusion은 유지된다. FTS5는 lexical 후보 입력만 대체하며 기본 strategy는 legacy다.

## Semantic Search 영향

semantic 함수, vector scan, cosine, top_k, embedding 호출은 변경하지 않았다.

## Evidence 영향

Evidence Packet 변환 및 source metadata 정책 변경 없음.

## Grounding 영향

Grounding 판단·정책·validator 변경 없음.

## Backup/Restore 영향

기존 backup/restore 코드는 변경하지 않았다. `rag_fts`는 파생 index이므로 restore 후 `rebuild_fts_index()`로 재생성 가능하다.

## DB Integrity 결과

실제 DB에서 `PRAGMA quick_check` 결과 **ok**.

## 관련 테스트 결과

RAG·Generation·Evidence·Preflight·Backup 회귀: **66 passed in 14.13s**. 추가 임시 DB 검증에서 FTS5 지원, index 1건 구축, 한글/reference 검색을 확인했다.

## 전체 pytest 결과

**212 passed in 22.14s**, failed 0, error 0.

## 발견된 문제

없음. Git status/branch는 저장소 metadata 부재로 확인할 수 없다. 영문/대규모 운영 데이터 latency는 별도 benchmark가 필요하다.

## 남은 위험

현재 source import/update 시 자동 FTS 증분 동기화는 제공하지 않으며 관리용 rebuild가 필요하다. FTS tokenizer가 한국어 형태소 분석을 제공하지 않으므로 품질은 query별 비교가 필요하다. `rag_fts`를 backup에 포함하는 정책은 기존 backup 구현을 변경하지 않고 restore 후 rebuild 방식으로 처리한다.

## Rollback 방법

`RAG_LEXICAL_STRATEGY=legacy`를 유지하고 `strategy="fts5"` 호출을 제거하면 기존 경로로 즉시 복귀한다. 필요하면 `DROP TABLE rag_fts` 후 `app/rag/fts.py`와 관련 import를 제거한다. 원본 Bible/RAG 데이터는 삭제하지 않는다.

## 다음 권장 단계

이번 Phase 2A 범위에서 중단한다. FTS5를 기본값으로 변경하거나 legacy를 삭제하지 않는다. 다음 단계인 RRF, Grounding Validator, Router 분리는 별도 승인 후 진행한다.
