# Bible Repository 다음 분리 경계 분석

## 현재 순서 상태

Settings Repository, Project Repository, Doctrine Repository는 완료 상태다. Bible Repository는 단일 CRUD/read 함수들이 이미 `app.repositories.bible`로 분리되었고, `import_items`와 `delete_bible_translation` 등 일부 persistence가 `core.py`에 남아 있다.

## 남은 후보 비교

| 후보 | 결합 요소 | 위험도 | 판단 |
|---|---|---:|---|
|`import_json`|파일 JSON parsing + `add_passage` 호출|낮음이지만 persistence 자체는 이미 Repository 위임|이번 persistence 후보에서 제외|
|`import_items`|입력 normalization, license 전체 배치 사전검사, passages upsert, RAG invalidation, 단일 transaction|중간|raw SQL persistence만 추출 가능|
|`delete_bible_translation`|파괴적 삭제, RAG vector 삭제, 동시 transaction, API confirmation|높음|후순위, 별도 승인 필요|
|`init_db`|전체 schema와 migration bootstrap|매우 높음|이번 단계에서 이동 금지|

## 권장 최소 단위

`import_items` 안에서 license 정책·입력 normalization은 Core에 유지하고, 다음 순수 DB persistence만 `app.repositories.bible`로 이동한다.

```python
persist_passage_batch(normalized, db_path) -> int
```

`normalized`는 기존 5-tuple `(translation, language, reference, text, license_note)` 목록이다. Repository는 기존 transaction 안에서:

- `passages` upsert
- 갱신된 `(translation, reference)`의 `rag_embeddings` 삭제
- 실제 입력 건수 반환

을 수행한다. schema, SQL, invalidation semantics는 그대로 유지한다.

## 보호할 경계

- 전문 저장 금지 license 사전검사는 Repository로 이동하지 않는다. 실패 시 어떤 row도 쓰지 않는 Core 정책을 유지한다.
- `init_db` 호출, busy timeout, normalization, public `import_items` signature는 Core에 유지한다.
- `delete_bible_translation`, RAG 검색/인덱싱, Evidence/Grounding, Router는 변경하지 않는다.

## 순환 import

`app.repositories.bible`는 현재처럼 `app.core`를 import하지 않고 SQLite·`app.paths`·`app.references`만 사용한다. 새 함수도 Provider·RAG service·main을 import하지 않는다.

## 승인 요청

위 최소 범위(`persist_passage_batch` 추가 및 `import_items`의 SQL upsert/invalidation 블록 한정 위임)를 구현할지 승인받는다. 파괴적 삭제 함수는 별도 분석과 승인 없이는 이동하지 않는다.
