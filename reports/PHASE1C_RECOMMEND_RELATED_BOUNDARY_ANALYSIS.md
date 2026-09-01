# recommend_related reference 제외 경계 분석

## 분석 범위

`recommend_related`의 DB 기준본문 조회, semantic query 구성, 후보 제외·중복 제거·limit 적용을 분석했다. 이번 단계에서는 소스를 수정하지 않았다.

## 현재 동작

1. `compare_reference(reference, db_path)`로 기준본문의 번역/절 목록을 조회한다.
2. 기준본문이 없으면 즉시 빈 목록을 반환한다.
3. 첫 최대 4개 row의 `reference`와 `text`를 이어 semantic query를 만든다.
4. `semantic_search`를 `max(limit * 4, 20)` 후보 수로 호출한다.
5. 기준 `reference.strip()`을 seen에 넣는다.
6. 후보를 순서대로 검사해 동일 reference와 중복 reference를 제외한다.
7. 원래 semantic 순서를 유지하며 `limit`건에서 중단한다.

## 경계별 결합도

| 책임 | 결합 요소 | 위험도 |
|---|---|---:|
|기준본문 조회|SQLite/Bible Repository `compare_reference`|중간|
|query 구성|기준본문 row의 `reference`, `text` 필드|중간|
|semantic 후보 조회|Provider와 `semantic_search` public 계약|중간|
|reference 제외·중복 제거·limit|후보 list와 문자열 정책만 사용|낮음|

## 권장 최소 단위

다음 순수 helper만 `app.rag.hybrid` 또는 별도 recommendation 모듈로 추출하는 것이 안전하다.

```python
filter_related_candidates(candidates, reference, limit) -> list[dict]
```

- `reference.strip()`을 seen 초기값으로 사용
- 각 후보의 `reference.strip()` 비교
- 중복 reference 제거 및 원래 순서 유지
- `limit` 도달 시 중단
- 후보에 `reference`가 없을 때의 기존 `KeyError` semantics와 입력 순서를 변경하지 않음

`compare_reference`, semantic query 구성, Provider 호출, API 응답 wrapper는 `core.py`에 유지한다. 이 helper는 `fuse_hybrid_results`와 달리 점수나 DB에 의존하지 않는다.

## 순환 import 및 호환성

`app.rag.hybrid`는 표준 list/dict/string 처리만 수행하고 `core`, Provider, Repository를 import하지 않는다. `core → app.rag.hybrid` 단방향을 유지한다. `/api/recommend` 및 `/api/study`의 응답 형식에는 변화가 없다.

## 승인 요청

위 최소 범위(`filter_related_candidates` 추가 및 `recommend_related`의 후보 filtering loop 한정 위임)를 구현할지 승인받는다. 기준본문 조회와 semantic 검색 호출은 이동하지 않는다.
