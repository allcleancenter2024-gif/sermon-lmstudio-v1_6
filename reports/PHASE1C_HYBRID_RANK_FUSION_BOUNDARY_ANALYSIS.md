# hybrid_search rank fusion 경계 분석

## 분석 범위

`hybrid_search`의 lexical·semantic 결과 결합과 rank fusion만 분석했다. 이번 단계에서는 소스를 수정하지 않았다.

## 현재 동작

1. `search_passages(query, limit)`로 lexical 결과를 얻는다.
2. `semantic_search(query, client, model, limit)`로 semantic 결과를 얻는다.
3. semantic 결과에 `0.75 * max(semantic_score, 0)`을 적용한다.
4. lexical 결과에는 `0.25 * (1 - rank / max(len(lexical), 1))`을 적용한다.
5. 동일 id는 점수를 누적하며, lexical row가 기존 semantic row를 대체할 수 있다.
6. 합산 점수 내림차순으로 `limit`을 적용하고 `rag_score`를 소수 4자리로 반올림한다.

## 결합도와 위험

rank fusion은 Provider 자체에는 의존하지 않지만 `search_passages`/`semantic_search`의 row 필드와 `id`, `semantic_score`, `limit` 계약에 강하게 의존한다. lexical-only row와 semantic-only row의 병합 규칙, 중복 id 처리, 0.75/0.25 정책, `rag_score` shaping이 모두 public 응답에 영향을 주므로 위험도는 중간~높음이다.

## 권장 최소 단위

다음 순수 helper를 `app/rag/hybrid.py`로 추출할 수 있다.

```python
fuse_hybrid_results(semantic, lexical, limit) -> list[dict]
```

helper는 기존 loop·가중치·중복 id 처리·정렬·반올림을 그대로 유지하고, `hybrid_search`는 두 검색 함수를 호출한 뒤 helper에 위임한다. `search_passages`, `semantic_search`, Provider 호출, API route는 이동하지 않는다.

## 순환 import 검토

`app.rag.hybrid`는 `app.core`, Provider, Repository를 import하지 않고 list/dict와 표준 함수만 사용해야 한다. `core → app.rag.hybrid` 단방향을 유지한다.

## 승인 요청

위 최소 범위(`fuse_hybrid_results` 추가 및 `hybrid_search`의 fusion loop 한정 위임)를 구현할지 승인받는다. 검색 호출과 API 응답 계약은 변경하지 않는다.
