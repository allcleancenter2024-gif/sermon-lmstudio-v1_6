# Phase 완료 보고: RAG 벡터 변환 경계

## 분석 범위

`build_rag_index`에서 Provider가 반환한 각 벡터를 저장용 `(packed, dimension, norm)`으로 변환하는 순수 구간을 private helper로 추출했다.

## 현재 동작

각 `vector`에 대해 `core.py`가 다음을 실행한다.

- `float(x)`를 순회해 `array("f")` float32 BLOB 생성
- 원본 iterable을 다시 순회해 L2 norm 계산
- `len(vector)`로 dimension 계산
- `(passage_id, packed, dimension, norm)` tuple 생성

## 분리 가능성

이 구간은 DB·Provider·`app.core` 함수에 직접 의존하지 않는 순수 변환 후보이다. 다만 현재 Provider 반환값은 일반 list를 전제로 하며, `float(x)` 변환 실패·비수치 값·빈 벡터·generator처럼 한 번만 순회 가능한 iterable에 대한 동작을 새로 검증하거나 보정하면 호환성 변화가 될 수 있다.

## 안전한 최소 경계

다음 private helper를 `app.repositories.rag`가 아닌 별도 순수 모듈 또는 `core.py` 내부 helper로 추출하는 방안이 적절하다.

```python
pack_rag_vector(vector) -> tuple[bytes, int, float]
```

- 입력을 기존과 동일하게 두 번 순회할 수 있는 sequence로 취급
- `float32` packing, `len(vector)`, norm 계산식을 그대로 유지
- 입력 검증, 차원 통일, zero-vector 정책, 예외 변환은 추가하지 않음
- Repository는 이미 준비된 tuple만 저장하므로 Provider와 무관하게 유지

`app.repositories.rag`에 넣을 경우 Repository가 `array`/`math`라는 저장 세부사항을 소유하게 된다. 따라서 현재 단계에서는 `core.py`의 private helper로만 추출하거나, 순수 `app/rag/packing.py`를 새로 만드는 선택지가 있다. 새 패키지 생성은 변경 범위가 커지므로 `core.py` private helper가 더 낮은 위험이다.

## 검증해야 할 기존 계약

- 정상 list 벡터의 packed bytes·dimension·norm 값
- batch별 `written` count
- Provider 반환 개수 부족 시 기존 `zip` 기반 부분 저장
- `float(x)` 또는 `len(vector)` 예외가 호출자에게 그대로 전달되는지
- zero vector의 norm `0.0` 저장 및 검색 시 기존 fallback 유지

## 적용한 변경

- `app.core.pack_rag_vector(vector)`를 추가했다.
- `build_rag_index`는 기존과 동일한 `zip` 순서로 helper를 호출한다.
- Provider 검증 정책·DB schema·`persist_rag_embeddings` API는 변경하지 않았다.

## 테스트 결과

- 변경 전 관련 테스트: `42 passed in 9.76s`
- 변경 후 관련 테스트: `42 passed in 10.99s`
- 변경 후 전체 테스트: `212 passed in 22.75s`

## 기존 기능 영향 및 rollback

- float32 packing, dimension, norm, 예외 전달 및 zero-vector 동작을 기존 식 그대로 유지했다.
- API, schema, data, Router는 변경하지 않았다.
- Rollback은 `build_rag_index`의 세 변환 문장을 복원하고 `pack_rag_vector` 정의를 삭제하면 된다.

## 다음 승인 대상

현재 RAG index 경계의 최소 분리가 완료됐다. 다음 작업은 새 기능이 아닌 추가 orchestration 분리이므로, 별도 의존성 분석과 승인을 받은 뒤 진행한다.
