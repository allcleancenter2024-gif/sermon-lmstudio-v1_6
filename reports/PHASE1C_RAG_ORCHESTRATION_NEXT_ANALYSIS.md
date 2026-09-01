# Phase 완료 보고: RAG 순수 semantic helper 분리

## 현재 완료 상태

RAG index 생성 경로에서 raw passage 조회, vector packing, SQLite upsert가 각각 분리되었다. 이번 단계에서는 순수 cosine 계산 helper를 `app.rag.semantic`으로 이동했다.

## 남은 함수와 결합도

| 함수 | 결합 요소 | 위험도 | 판단 |
|---|---|---:|---|
|`_cosine`|순수 수학, DB/Provider 없음|낮음|가장 작은 다음 후보 |
|`semantic_search`|Provider query embedding, Repository raw vector read, binary/legacy 복원, scoring, 응답 shaping|중간|`_cosine` 이후 분석 |
|`hybrid_search`|`search_passages` + `semantic_search` + rank fusion|높음|semantic 경계 확정 후 |
|`recommend_related`|`semantic_search` 결과와 reference 제외 정책|중간|semantic 이후 |
|`build_rag_index` orchestration|Provider 호출, batch 정책, partial zip semantics|중간|현재 core 유지 |

## 의존 방향 검토

`semantic_search`를 즉시 통째로 이동하면 Provider protocol, `fetch_rag_vector_rows`, legacy vector 복원, 응답 필드 계약을 동시에 옮겨야 한다. 반면 `_cosine`은 입력 list와 결과 float만 사용하는 순수 함수라 별도 모듈로 이동해도 순환 import 위험이 없다.

권장 방향은 다음과 같다.

```text
app.core ──> app.rag.semantic (순수 cosine helper)
app.core ──> app.repositories.rag
app.core ──> Provider
```

Provider 또는 Repository가 `app.core`를 import하는 경로는 만들지 않는다.

## 적용한 최소 변경

`cosine_similarity`를 `app/rag/semantic.py`에 추가하고, `app.core._cosine`은 alias로 유지했다. 이번 단계에서는 `semantic_search` 전체, `hybrid_search`, `recommend_related`, Router를 이동하지 않았다.

주의할 점:

- 길이가 다르거나 빈 벡터일 때 `-1.0` 반환 유지
- zero norm일 때 `-1.0` 반환 유지
- `semantic_search`의 binary vector 경로와 stored norm 최적화 경로는 변경하지 않음
- public API URL/응답과 SQLite는 변경하지 않음

## 테스트 결과

- 변경 전 관련 테스트: `42 passed in 9.80s`
- 변경 후 관련 테스트: `42 passed in 9.77s`
- 변경 후 전체 테스트: `212 passed in 23.21s`

## 기존 기능 영향 및 rollback

- 길이 불일치·빈 벡터·zero norm의 `-1.0` sentinel과 cosine 계산식을 유지했다.
- API, SQLite schema/data, Provider 호출은 변경하지 않았다.
- Rollback은 `core.py`에 기존 `_cosine` 구현을 복원하고 `app/rag/semantic.py` 및 import를 제거하면 된다.

## 다음 승인 대상

다음 후보는 `semantic_search`의 query embedding·vector row 복원·scoring 책임 경계를 추가 분석하는 것이다. 별도 승인 없이는 구현하지 않는다.
