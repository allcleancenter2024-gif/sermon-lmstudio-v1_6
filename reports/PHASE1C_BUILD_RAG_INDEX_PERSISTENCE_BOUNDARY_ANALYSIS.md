# Phase 완료 보고: build_rag_index upsert 분리

## 분석 범위

`build_rag_index`의 Provider 호출 이후 구간 중 SQLite upsert만 Repository로 분리했다. Provider 호출과 벡터 변환은 이동하지 않았다.

## 현재 동작

각 batch에 대해 `core.py`가 다음을 수행한다.

1. `client.embeddings(model, inputs)` 결과를 받는다.
2. 각 벡터를 `array("f")`로 float32 BLOB 변환한다.
3. L2 norm과 차원(`len(vector)`)을 계산한다.
4. 하나의 SQLite 연결/transaction 안에서 `rag_embeddings`에 upsert한다.
5. `vector_json`에는 legacy 호환을 위해 문자열 `"[]"`을 저장한다.

## 경계별 의존성

| 책임 | 의존성 | 권장 소유자 |
|---|---|---|
| Provider 호출 및 입력 batch 생성 | `LMStudioClient` protocol, model, passage 문자열 계약 | `core.py` |
| 벡터 → float32 BLOB/norm 변환 | `array`, `math`, Provider 반환 벡터 | 1차 구현에서는 `core.py` 유지 |
| `rag_embeddings` batch upsert | SQLite schema, `(passage_id, model)` UNIQUE, transaction | Repository 후보 |

## 중요한 호환성 관찰

- 기존 schema는 `vector_json TEXT NOT NULL`이며, 최신 schema에는 nullable `vector_blob`과 `norm`이 추가되어 있다. Repository upsert는 `vector_json="[]"`을 계속 써야 구 schema와 호환된다.
- 현재 transaction 범위는 batch 하나다. 한 batch 내 SQL 오류가 나면 해당 batch 전체가 rollback되고, 앞선 batch commit은 유지된다.
- Provider 반환 개수와 batch 개수가 다르면 현재 `zip(batch, vectors)`가 남는 쪽만 저장하고 예외를 발생시키지 않는다. 이 동작을 새 Repository에서 검증/변경하면 호환성 변화이므로 이번 분리에서는 건드리지 않아야 한다.
- `written`은 실제 upsert를 수행한 행 수이며, Provider 반환 길이 검증 결과가 아니다.

## 순환 import 검토

`app.repositories.rag`는 `app.core`나 Provider를 import하지 않는다. Repository 함수는 이미 변환된 rows와 model, db_path만 받아야 하며, Provider 객체나 `LMStudioClient` 타입에 의존해서는 안 된다.

## 적용한 최소 변경

기존 Doctrine 패턴과 동일하게 다음 함수를 추가했다.

```python
persist_rag_embeddings(rows, model, db_path) -> int
```

- `rows` 형식: `(passage_id, packed, dimension, norm)` iterable
- Repository 내부에서 한 batch를 하나의 transaction으로 upsert
- `vector_json="[]"`, `vector_blob`, `dimension`, `norm`을 기존 SQL과 동일하게 기록
- `build_rag_index`는 Provider 호출과 `array`/`math` 변환을 유지하고, SQL block만 새 함수에 위임
- 반환값은 기존 `written` 합산과 동일하게 유지

`build_rag_index`는 Provider 호출 후 기존과 동일하게 벡터를 준비하고, 저장만 이 함수에 위임한다. 저장 책임만 이동하며 Provider 경계·벡터 계산·batch 오류 동작은 변하지 않는다.

## 테스트 결과

- 변경 전 관련 테스트: `42 passed in 9.82s`
- 변경 후 관련 테스트: `42 passed in 9.99s`
- 변경 후 전체 테스트: `212 passed in 22.73s`

## 기존 기능 영향

- API URL, 응답 형식, SQLite schema/data는 변경하지 않았다.
- `vector_json="[]"`, binary vector, dimension, norm 및 `(passage_id, model)` upsert 계약을 유지했다.
- batch 단위 transaction과 Provider 반환 길이 불일치 시 기존 `zip` 동작을 유지했다.

## Rollback 방법

`build_rag_index`의 prepared rows 생성 후 기존 SQL upsert 블록을 복원하고 `persist_rag_embeddings` import/함수를 제거하면 된다. DB rollback은 필요하지 않다.

## 다음 승인 대상

다음 후보는 벡터 변환(`array("f")`, norm, dimension)의 순수 함수 경계다. Provider 반환값 검증 정책을 변경하지 않는 최소 추출인지 먼저 분석한 뒤, 별도 승인 없이는 구현하지 않는다.
