# Phase 1C-4 Bible Repository 완료 보고

## 작업 전 Baseline

- Git status/branch: 작업 디렉터리가 Git 저장소가 아니어서 확인 불가.
- 제품 버전 표기: `sermon-lmstudio-final-package-v40`.
- 전체 pytest: `212 passed in 22.13s`, failed/error `0`.
- 변경 전 Bible 관련: Bible `44 passed`, Evidence `13 passed`, Preflight `11 passed`.

## 기존 Bible 구조

기존에는 `app.repositories.bible`에 저위험 Bible CRUD/query가 이미 있었고, `app.core`에 bulk import와 번역 삭제 SQL이 남아 있었다. `main.py`는 `app.core` public interface를 통해 API를 호출했다.

## Bible DB Table

- `passages`
- `translation_licenses`
- `rag_embeddings` (본문 갱신/삭제 시 stale vector invalidation 용도)

기존 table/column/UNIQUE/index 정의를 그대로 사용했다.

## Bible 관련 Public Interface

- `add_passage`, `import_items`, `import_json`
- `search_passages`, `compare_reference`
- `register_translation_license`, `translation_licenses`
- `db_stats`, `bible_database_integrity`, `bible_database_dashboard`
- `delete_bible_translation`

## 이동한 함수/책임

- `persist_passage_batch(normalized, db_path)` — passages batch upsert 및 RAG vector invalidation
- `delete_bible_translation(translation, db_path)` — 해당 번역의 passage/vector 삭제 transaction

기존에 분리되어 있던 Bible Repository 함수들도 그대로 유지했다.

## core.py Compatibility Wrapper

`import_items` public 함수는 Core에 남겨 normalization, translation license 사전검사, `init_db` 호출을 수행한 뒤 `persist_passage_batch`를 호출한다. `delete_bible_translation`은 Repository 함수를 `core.py`에서 re-export하여 `app.main`과 기존 patch/import 경로를 유지한다.

## 새 Repository 구조

```text
app.main → app.core compatibility interface
app.core → app.repositories.bible → SQLite
```

Repository는 `app.core`, `app.main`, Provider, RAG service, Grounding, Sermon generator를 import하지 않는다.

## 변경 파일

- `app/repositories/bible.py`
- `app/core.py`
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE1C_BIBLE_NEXT_BOUNDARY_ANALYSIS.md`
- `reports/PHASE1C_BIBLE_IMPORT_BATCH_REPORT.md`
- `reports/PHASE1C_BIBLE_REPOSITORY_REPORT.md`

## SQLite Schema 영향

없음. migration, column rename/type 변경, 데이터 재작성, reference normalization 변경을 수행하지 않았다.

## 기존 DB 호환성

기존 `passages`, `translation_licenses`, `rag_embeddings`를 그대로 읽고 쓴다. 새 DB 생성이나 Bible 재import가 필요하지 않다.

## Bible Reference 호환성

reference normalization/expand 정책은 변경하지 않았다. 기존 `compare_reference`와 validation 경로를 그대로 사용한다.

## Translation 호환성

translation license 사전검사와 오류 메시지는 Core에 유지했다. batch upsert 및 삭제 시 translation/reference 조건은 기존 SQL과 동일하다.

## Evidence Packet 비교

`passages` row의 `translation`, `language`, `reference`, `text`, `license_note`가 보존되며, Evidence Packet의 중심본문·관련 본문·count 조립 로직은 변경하지 않았다. Evidence 관련 테스트 `13 passed`.

## Preflight 비교

Bible readiness, main passage completeness, evidence availability 판정 로직은 이동하지 않았다. Preflight 관련 테스트 `11 passed`.

## Grounding 영향

Grounding 정책과 `build_grounding`/prompt 입력은 변경하지 않았다. Bible evidence의 권위 단계와 metadata가 유지된다.

## RAG 영향

embedding/ranking/검색 로직은 변경하지 않았다. 본문 upsert·삭제 시 기존 RAG vector invalidation SQL만 Repository에서 수행한다.

## API 영향

없음. URL, method, request body/query, response schema, status code, error format, endpoint 위치를 변경하지 않았다.

## 성능 영향

upsert/delete SQL과 쿼리 수는 기존과 동일하다. Repository 위임에 따른 연결 경계만 바뀌었으며, per-verse bootstrap이나 N+1 query를 추가하지 않았다.

## 순환 Import 검사

`app.repositories.bible`는 `app.core`·`app.main`·Provider·RAG·Grounding·Sermon을 import하지 않는다. `core → repositories.bible` 단방향이며 순환 import는 확인되지 않았다.

## 관련 테스트 결과

- Bible unit/query: `41 passed`
- Bible import: `8 passed`
- 중심본문 validation: `41 passed`
- Evidence Packet: `13 passed`
- Preflight: `11 passed`
- Grounding regression: `13 passed`
- Sermon generation regression: `8 passed`
- Backup/Restore compatibility: `6 passed`

## 전체 pytest 결과

`212 passed in 22.85s`, failed/error `0`.

## 추가한 테스트

없음. 기존 테스트로 import batch, license rejection, RAG invalidation, translation 삭제 및 API confirmation을 검증했다.

## 발견된 문제

없음.

## 남은 위험

- `import_items`의 license 사전검사와 Repository upsert가 별도 DB 연결로 실행되어 극단적 동시 license 변경 상황의 검사 시점 간격이 기존보다 넓다.
- `delete_bible_translation`은 파괴적 작업이므로 향후 변경 시 별도 confirmation/rollback 검토가 필요하다.

## Rollback 방법

1. `app/core.py`의 기존 `import_items` SQL upsert/invalidation 및 `delete_bible_translation` 구현을 복원한다.
2. Bible Repository import를 이전 상태로 복원한다.
3. `app/repositories/bible.py`의 새 함수와 보고서 변경을 제거한다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB schema/data rollback은 필요하지 않다.

## 다음 권장 단계

지시서에 따라 Bible Repository 결과만 보고하고 자동 진행을 중단한다. Sermon Repository, Original Language, Sermon Service, RAG 모듈화, FTS5, RRF, Grounding, Router는 별도 분석과 승인을 받은 뒤 진행한다.
