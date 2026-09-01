# Phase 완료 보고

## 변경 목적

`original_notes`의 raw SQLite 조회와 core의 lexicon enrichment를 분리해 Repository 경계를 정리했다. public `original_notes` 함수 자체와 반환 결과는 유지했다.

## 변경 파일

- `app/repositories/bible.py` — `fetch_original_note_rows` 추가
- `app/core.py` — `original_notes`가 raw Repository 조회 후 기존 enrichment를 수행하도록 변경
- `reports/CORE_DEPENDENCY_MAP.md` — 원어 조회 경계 갱신

## 변경 내용

- Repository 이동: 단일 reference/range 확장, `original_word_notes` raw 조회, canonical reference 순서 및 language·id 정렬.
- Core 유지: `_enrich_original_notes`, `lexicon_lookup_key`, `original_lexicon` 조회, enrichment/provenance 필드 생성.
- `app.core.original_notes`의 public 이름·매개변수·반환 구조를 유지했다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리·`app.paths`·`app.references`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- range alias, invalid-reference fallback, lexicon enrichment 동작 유지.
- `original_language_coverage`, bulk import, Bible research, RAG, Doctrine·Project·Sermon·Router는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v23_original_language.py`, `tests/test_v33_lexicon_enrichment.py`, `tests/test_v39_oshb_zip.py`, `tests/test_v40_original_coverage.py` — `64 passed in 13.19s`
- 1차 변경 후 테스트: `1 failed, 63 passed` — raw bootstrap에서 `original_lexicon` table이 누락되어 enrichment가 실패
- 보완: raw 조회 bootstrap에서 기존 `original_lexicon` table/index 생성 보장
- 보완 후 관련 테스트: 동일 모듈 — `64 passed in 12.80s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 22.17s` (`PYTEST_EXIT=0`)

## 발견된 문제

- raw 조회만 분리하면 기존 `init_db`가 암묵적으로 보장하던 lexicon table이 없어질 수 있었다. Repository bootstrap에 기존 lexicon table 정의를 추가해 해결했다.

## 남아 있는 위험

- `original_notes`는 아직 core facade에서 enrichment를 수행한다. enrichment까지 옮기려면 lexicon 정책과 원어 key 규칙을 별도 단위로 검토해야 한다.
- `init_db`와 Repository 양쪽에 관련 table bootstrap이 남아 있다. 기존 public 함수의 독립 호출 호환성을 위한 제한된 중복이다.

## Rollback 방법

1. `app/core.py`에서 `original_notes`를 이전 직접 조회 구현으로 복원하고 `fetch_original_note_rows` import를 제거한다.
2. `app/repositories/bible.py`의 `fetch_original_note_rows`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 ORIGINAL_LANGUAGE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

이번 단계로 Bible의 저결합 read/query 단위가 상당 부분 분리되었다. 다음은 `project_dashboard`·`save_sermon`·RAG/Doctrine vector 함수처럼 결합도가 높은 후보를 즉시 이동하지 말고, 별도 분석과 승인을 거친다. Phase 2 Router 분리는 시작하지 않는다.
