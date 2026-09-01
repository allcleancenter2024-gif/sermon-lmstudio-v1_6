# semantic_search scoring 경계 분석

## 분석 범위

`semantic_search`의 query embedding 이후 scoring 구간과 `hybrid_search` rank fusion을 비교했다. 이번 단계에서는 소스 변경을 하지 않았다.

## 현재 scoring 동작

각 Repository row에 대해 `core.py`가 다음을 수행한다.

1. `restore_rag_vector`로 binary/legacy vector 복원
2. stored `norm`이 있으면 query norm, dot product를 계산해 cosine score 산출
3. stored norm이 없으면 `_cosine` fallback 사용
4. 원본 passage 필드에 `semantic_score`를 추가
5. score 내림차순 정렬 후 `limit` 적용

## 경계별 결합도

| 후보 | 결합 요소 | 위험도 |
|---|---|---:|
|`score_semantic_vector` 순수 helper|두 vector, optional stored norm, `cosine_similarity`|낮음|
|query embedding wrapper|Provider client, model, query 문자열|중간|
|row scoring orchestration|Repository row shape, restore helper, 응답 필드|중간|
|`hybrid_search` rank fusion|lexical `search_passages`, semantic 결과, 0.75/0.25 정책, `rag_score` 응답|높음|

## 권장 최소 단위

다음 순수 helper만 `app.rag.semantic`으로 추출한다.

```python
score_semantic_vector(query_vector, vector, stored_norm) -> float
```

- stored norm이 truthy이면 현재의 query norm·dot·division 식을 그대로 사용
- stored norm이 없으면 `cosine_similarity` fallback 사용
- dimension mismatch, empty vector, zero norm sentinel은 기존 `-1.0` 유지
- query norm을 사전 계산하거나 입력 검증을 추가하지 않아 계산/예외 semantics를 변경하지 않음

`semantic_search`는 Provider 호출, row 복원, 결과 shaping, 정렬/limit을 계속 소유한다. `hybrid_search`는 lexical/semantic rank fusion 정책이 별도이므로 이번 단계에서 이동하지 않는다.

## 순환 import 및 호환성

`app.rag.semantic`은 표준 라이브러리와 내부 cosine helper만 사용하며 `core`, Provider, Repository를 import하지 않는다. `app.core`는 helper를 alias/re-export하여 기존 private 호출 경로를 유지할 수 있다. API URL, 응답 형식, SQLite schema/data에는 영향이 없다.

## 승인 요청

위 최소 범위(`score_semantic_vector` 추가 및 `semantic_search`의 score 계산식 한정 위임)를 구현할지 승인받는다. `hybrid_search`와 query embedding 이동은 포함하지 않는다.
