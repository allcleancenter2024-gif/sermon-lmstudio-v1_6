# Phase 완료 보고: semantic_search vector 복원 분리

## 변경 목적

`semantic_search`의 저장 벡터 복원(binary/legacy JSON) 책임만 순수 helper로 분리하고 Provider 호출·scoring·응답 계약은 유지한다.

## 변경 파일

- `app/rag/semantic.py`
- `app/core.py`
- `reports/CORE_DEPENDENCY_MAP.md`

## 변경 내용

- `restore_rag_vector(vector_blob, vector_json)` 추가
- binary `array("f")` 복원 및 legacy `json.loads` fallback을 기존 조건 그대로 이동
- `semantic_search`는 Repository row 조회, Provider query embedding, norm/scoring, 정렬, limit을 계속 담당

## 기존 기능 영향

- API URL/응답 형식, SQLite schema/data, Provider 호출은 변경하지 않았다.
- 잘못된 blob/JSON에 대한 예외 변환이나 추가 검증을 하지 않아 기존 예외 전달을 유지했다.
- `cosine_similarity`와 `core._cosine` compatibility alias도 유지했다.

## 테스트

- 변경 전 관련 테스트: `42 passed in 9.75s`
- 변경 후 관련 테스트: `42 passed in 9.75s`
- 변경 후 전체 pytest: `212 passed in 22.56s`

## Rollback 방법

`semantic_search`에 기존 binary/JSON 분기 블록을 복원하고 `restore_rag_vector` import/함수를 제거하면 된다. DB rollback은 필요하지 않다.

## 다음 단계

다음 후보는 `semantic_search`의 scoring orchestration 또는 `hybrid_search`의 rank fusion이다. 결합도가 더 높으므로 의존성 분석과 별도 승인을 먼저 수행한다.
