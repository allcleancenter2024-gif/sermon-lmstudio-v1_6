# Phase 완료 보고

## 변경 목적

`semantic_search`에서 SQLite의 RAG 원시 벡터 행 조회 책임만 가장 작은 단위로 분리한다. 기존 Provider 임베딩 호출과 점수 계산 동작은 `app.core`에 유지한다.

## 변경 파일

- `app/repositories/rag.py`
- `app/core.py`
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE1C_RAG_VECTOR_READ_REPORT.md`

## 변경 내용

- `app.repositories.rag.fetch_rag_vector_rows(model, db_path)`를 추가했다.
- 기존 `rag_embeddings JOIN passages` 조회와 모델 필터를 Repository로 이동했다.
- `core.semantic_search`는 Repository 결과를 받아 다음 책임을 계속 가진다.
  - Provider를 통한 query embedding 생성
  - `vector_blob` 바이너리 복원 및 legacy `vector_json` fallback
  - cosine score 계산, 정렬, limit 적용
- Repository는 `app.core`를 import하지 않아 순환 import 경로를 만들지 않는다.

## 기존 기능 영향

- API URL과 응답 형식은 변경하지 않았다.
- SQLite schema와 기존 데이터는 변경하지 않았다. 기존 테이블 보장 로직만 Repository 내부에서 재사용한다.
- `app.core.semantic_search` public interface와 반환 필드는 유지했다.
- Bible·Sermon·Doctrine·RAG의 나머지 orchestration 및 Router 분리는 이번 단계에서 시작하지 않았다.

## 테스트

- 변경 전 관련 테스트: `42 passed in 10.12s`
- 변경 후 관련 테스트: `42 passed in 9.77s`
- 변경 후 전체 테스트: `212 passed in 22.58s`

## 발견된 문제

없음.

## 남아 있는 위험

- `build_rag_index`는 아직 raw passage 조회, Provider embedding, 벡터 저장을 함께 소유한다.
- `semantic_search`의 scoring 책임은 아직 `core.py`에 남아 있으므로 다음 분리 때 Provider와 raw 데이터 경계를 다시 검증해야 한다.

## Rollback 방법

`app.core.semantic_search`에서 `fetch_rag_vector_rows` 호출을 제거하고 기존 SQL 조회 블록을 복원한 뒤, `app.repositories.rag`의 해당 함수와 import를 삭제한다. 의존성 지도와 본 보고서의 변경 내역도 함께 되돌리면 된다. DB 데이터나 schema rollback은 필요하지 않다.

## 다음 권장 단계

`build_rag_index`의 raw passage 조회와 Provider embedding 호출 사이의 경계를 먼저 분석하고, 분석 결과를 보고한 뒤 raw 조회만 별도 Repository 함수로 분리할지 승인받는다. Phase 2 Router 분리는 시작하지 않는다.
