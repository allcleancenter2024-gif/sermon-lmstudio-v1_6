# Phase 완료 보고

## 변경 목적

Bible 영역에서 단일 본문 또는 범위에 대한 등록 번역 비교 조회를 Repository로 분리했다.

## 변경 파일

- `app/repositories/bible.py` — `compare_reference` 추가
- `app/core.py` — `compare_reference`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — Bible 분리 현황 갱신

## 변경 내용

- 이동: reference range expansion, invalid-reference fallback, passages 조회, canonical reference 순서 및 language·translation 정렬.
- 기존 public 함수명·매개변수·반환 필드·빈 입력 동작·오류 fallback을 유지했다.
- `expand_reference`, `normalize_reference`는 기존 `app.references` 구현을 재사용했다.
- RAG, research packet, outline validation, import, 삭제 로직은 이동하지 않았다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리·`app.paths`·`app.references`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- `/api/compare`, `build_passage_study`, outline 및 추천 흐름의 기존 core import 경로 유지.
- Phase 2 Router 분리 미착수.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v23_original_language.py`, `tests/test_e2e_v6.py` — `44 passed in 11.81s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `44 passed in 11.57s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 22.90s` (`PYTEST_EXIT=0`)

## 발견된 문제

- 없음.

## 남아 있는 위험

- `compare_reference`는 `/api/compare`와 연구·outline 흐름의 핵심 입력이므로 SQL 정렬·alias 처리 변경은 후속 단계에서 별도 승인해야 한다.
- `init_db`와 Repository 양쪽에 passage table bootstrap이 남아 있다. 기존 public 함수의 독립 호출 호환성을 위한 제한된 중복이다.

## Rollback 방법

1. `app/core.py`에 기존 `compare_reference` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/bible.py`에서 `compare_reference`와 `expand_reference` import를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 BIBLE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 후보는 `original_notes` 또는 `project_dashboard`처럼 enrichment·workflow 상태와 결합된 조회이므로, 바로 이동하지 않고 의존성 분석과 별도 승인을 먼저 진행한다. Phase 2 Router 분리는 시작하지 않는다.
