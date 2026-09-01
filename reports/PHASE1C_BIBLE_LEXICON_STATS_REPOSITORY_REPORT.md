# Phase 완료 보고

## 변경 목적

원어 사전 영역에서 단순 통계 조회 책임만 가장 작은 단위로 분리했다. 사전 등록·수정, 원어 노트 enrichment, coverage 계산은 이동하지 않았다.

## 변경 파일

- `app/repositories/bible.py` — `original_lexicon_stats` 및 `original_lexicon` bootstrap 추가
- `app/core.py` — `original_lexicon_stats`를 repository에서 re-export
- `reports/CORE_DEPENDENCY_MAP.md` — 원어 사전 통계 분리 현황 갱신

## 변경 내용

- 이동: lexicon 전체 COUNT 및 language별 GROUP BY 조회.
- 기존 public 함수명·매개변수·반환 구조·정렬 순서를 유지했다.
- 단독 호출 호환성을 위해 기존과 동일한 `original_lexicon` table/index bootstrap을 Repository에 유지했다.
- `import_original_lexicon`, `lexicon_lookup_key`, enrichment 및 원어 노트 조회는 core에 남겼다.
- Repository는 `app.core`를 import하지 않으며 표준 라이브러리·`app.paths`만 사용한다.

## 기존 기능 영향

- API URL·request/response 형식 변경 없음.
- SQLite schema·기존 데이터 변경 없음.
- `app.core.original_lexicon_stats` 기존 import 경로 유지.
- Bible 본문, RAG, Doctrine·Project·Sermon·Router 코드는 변경하지 않았다.

## 테스트

- 변경 전 관련 테스트: `tests/test_v33_lexicon_enrichment.py`, `tests/test_v40_original_coverage.py` — `15 passed in 2.21s`
- 변경 후 문법 검사: `.venv\\Scripts\\python.exe -m compileall -q app` — 통과
- 변경 후 관련 테스트: 동일 모듈 — `15 passed in 2.23s`
- 전체 테스트: `.venv\\Scripts\\python.exe -m pytest -q` — `212 passed in 33.38s`

## 발견된 문제

- 없음.

## 남아 있는 위험

- `init_db`와 Repository 양쪽에 lexicon table bootstrap이 남아 있다. 기존 public 함수의 독립 호출 동작을 보존하기 위한 제한된 중복이다.
- 사전 등록과 enrichment는 core에 남아 있어, 통계 조회만 먼저 분리된 부분 상태다.

## Rollback 방법

1. `app/core.py`에 기존 `original_lexicon_stats` 구현을 복원하고 repository import에서 해당 이름을 제거한다.
2. `app/repositories/bible.py`에서 `original_lexicon_stats`와 `_ensure_original_lexicon_table`를 제거한다.
3. `reports/CORE_DEPENDENCY_MAP.md`의 ORIGINAL_LANGUAGE 상태를 이전 표기로 되돌린다.
4. 전체 pytest가 `212 passed`인지 확인한다.

DB migration, schema rollback, 데이터 복원은 필요 없다.

## 다음 권장 단계

다음 후보는 `original_lexicon_stats`와 결합하지 않은 독립 CRUD 단위로 다시 의존성 확인 후 승인받아 진행한다. 실패가 발생하면 다음 Repository로 진행하지 않으며, Phase 2 Router 분리는 시작하지 않는다.
