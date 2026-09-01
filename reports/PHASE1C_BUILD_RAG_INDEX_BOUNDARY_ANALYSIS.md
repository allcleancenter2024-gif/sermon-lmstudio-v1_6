# Phase 완료 보고: build_rag_index raw 조회 분리

## 분석 범위

이번 단계에서는 분석한 경계 중 가장 작은 단위인 raw passage 조회만 Repository로 분리했다. Provider embedding과 SQLite 저장은 이동하지 않았다.

## 현재 구조

`app.core.build_rag_index(client, model, db_path, batch_size)`는 다음 순서로 동작한다.

1. `init_db(db_path)`로 기존 DB schema를 보장한다.
2. SQLite에서 `passages`의 `id, translation, language, reference, text`를 `id` 순으로 모두 조회한다.
3. `batch_size` 단위로 입력 문자열(`reference | translation | text`)을 만든다.
4. `client.embeddings(model, inputs)`를 호출한다.
5. 각 벡터를 float32 `vector_blob`과 norm으로 변환한다.
6. `rag_embeddings`에 `(passage_id, model)` upsert한다.
7. 실제 기록 건수를 반환한다.

## 의존성 경계

| 책임 | 현재 소유자 | 외부 의존성 | 분리 판단 |
|---|---|---|---|
| raw passage 조회 | `app.core` | SQLite `passages`, `db_path`, 정렬 계약 | 가장 낮은 위험. Repository 후보 |
| Provider embedding | `app.core` orchestration | `LMStudioClient`/embedding protocol, model, batch 입력 형식 | core 유지 |
| 벡터 변환·저장 | `app.core` | `array`, `math`, 기존 `rag_embeddings` schema, upsert 계약 | 이번 최소 단위에서는 core 유지 |

## 순환 import 검토

`app.repositories.rag`는 `app.core`를 import하지 않으므로 `fetch_rag_vector_rows`와 동일한 모듈에 raw passage 조회 함수를 추가해도 `core → repositories.rag` 단방향을 유지할 수 있다. Repository가 Provider나 `LMStudioClient`를 import하면 안 된다.

## 호환성 및 위험

- API URL과 응답 형식에는 직접 영향이 없다.
- SQLite schema/data를 변경하지 않고 기존 `SELECT ... ORDER BY id` 결과를 그대로 반환해야 한다.
- 빈 `passages`일 때 `build_rag_index`가 `0`을 반환하는 기존 동작을 유지해야 한다.
- 조회 결과의 필드 누락·순서 변경은 embedding 입력과 `passage_id` 매핑을 깨뜨릴 수 있으므로 필드와 정렬을 고정해야 한다.
- Provider 호출 실패 시 현재 함수는 예외를 호출자에게 전달한다. raw 조회 Repository가 이를 변환하거나 삼키면 안 된다.
- 벡터 개수와 batch 개수가 다를 때 현재 `zip` 동작을 바꾸지 않으려면 저장 책임을 당장 이동하지 않는 것이 안전하다.

## 적용한 최소 변경

`app.repositories.rag.fetch_rag_passages(db_path)`를 추가했다.

- 반환: 기존 조회와 동일한 `list[dict]`
- SQL: `SELECT id, translation, language, reference, text FROM passages ORDER BY id`
- DB 초기화/테이블 생성 책임은 기존 `core.init_db` 호출을 유지한다.
- `build_rag_index`는 `init_db`와 Provider·변환·upsert를 그대로 유지하고, 조회 블록만 새 함수 호출로 교체한다.

`build_rag_index`는 `init_db` 후 이 함수를 호출하고, Provider·변환·upsert·반환 계약은 기존 코드 그대로 유지한다. 이 범위는 기능 추가가 아닌 raw read delegation이다.

## 테스트 결과

- 변경 전 관련 테스트: `42 passed in 10.05s`
- 변경 후 관련 테스트: `42 passed in 9.73s`
- 변경 후 전체 테스트: `212 passed in 22.43s`

## 기존 기능 영향

- API URL과 응답 형식은 변경하지 않았다.
- SQLite schema와 데이터는 변경하지 않았다.
- 빈 `passages`에서 `0` 반환, `ORDER BY id`, batch 입력 순서, Provider 예외 전달을 유지했다.
- Router 분리와 다음 저장 경계 분리는 시작하지 않았다.

## Rollback 방법

`build_rag_index` 안에 있던 기존 `SELECT ... ORDER BY id` 블록을 복원하고 `fetch_rag_passages` import/함수를 삭제하면 된다. DB rollback은 필요하지 않다.

## 다음 승인 대상

다음 후보는 벡터 변환·`rag_embeddings` upsert 경계다. Provider 호출과 저장의 원자성 및 vector 수 불일치 동작을 먼저 분석한 뒤, 별도 승인 없이는 구현하지 않는다.
