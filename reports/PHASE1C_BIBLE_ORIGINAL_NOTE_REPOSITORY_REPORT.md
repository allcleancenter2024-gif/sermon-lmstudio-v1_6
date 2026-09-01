# Phase 완료 보고

## 변경 목적

Bible 영역에서 원어 노트 단건 저장 책임만 가장 작은 단위로 분리했다. 조회·사전 import·enrichment·coverage 계산은 이동하지 않았다.

## 변경 파일

- `app/repositories/bible.py` — `add_original_note` 및 `original_word_notes` bootstrap 추가
- `app/core.py` — `add_original_note`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — 원어 단건 CRUD 분리 현황 갱신

## 변경 내용

- 이동: reference 정규화, 기본 원어 검증 호출, `original_word_notes` 단건 INSERT, `lastrowid` 반환.
- 기존 public 함수명·매개변수·반환값·정규화 fallback·SQLite INSERT 규칙을 유지했다.
- 단독 호출 호환성을 위해 기존과 동일한 table/index bootstrap을 Repository에 유지했다.
- `normalize_reference`, `validate_primary_original_language`는 기존 `app.references` 구현을 재사용했다. 검증 정책을 복제하거나 변경하지 않았다.
- Repository는 `app.core`를 import하지 않으며 `app.references`와 SQLite만 의존한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- 기존 SQLite schema·운영 데이터 변경 없음.
- `app.core.add_original_note` 기존 import 경로 유지.
- `original_notes`, `import_original_notes`, `import_original_note_batches`, lexicon 관련 함수, coverage/research/RAG, Doctrine·Project·Sermon·Router는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_core.py`, `tests/test_v23_original_language.py`, `tests/test_v33_lexicon_enrichment.py`, `tests/test_v40_original_coverage.py` — `58 passed in 14.55s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `58 passed in 14.63s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 24.78s`

## 발견된 문제

- 없음.

## 남아 있는 위험

- `init_db`와 Repository 양쪽에 원어 노트 table bootstrap이 남아 있다. 기존 public 함수의 독립 호출 호환성을 위한 제한된 중복이다.
- 원어 노트 조회·enrichment는 여전히 core에 있어 단건 저장과 조회의 경계가 완전히 통합된 상태는 아니다.

## Rollback 방법

1. `app/core.py`에 이전 `add_original_note` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/bible.py`의 `add_original_note`와 `_ensure_original_notes_table`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 ORIGINAL_LANGUAGE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 후보는 원어 조회 또는 사전 import가 아닌, 의존성 지도를 다시 확인한 뒤 가장 낮은 단일 CRUD 하나로 제한한다. 실패가 발생하면 다음 Repository로 진행하지 않으며, Phase 2 Router 분리는 시작하지 않는다.
