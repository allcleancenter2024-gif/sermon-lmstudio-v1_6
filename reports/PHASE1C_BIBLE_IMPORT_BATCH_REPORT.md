# Phase 1C Bible Repository: import batch persistence 완료 보고

## 변경 목적

Bible Repository에 남아 있던 `import_items`의 DB persistence만 최소 단위로 분리했다. 입력 normalization과 translation license 정책은 Core에 유지했다.

## 변경 파일

- `app/repositories/bible.py` — `persist_passage_batch` 추가
- `app/core.py` — `import_items`의 upsert/invalidation 위임
- `reports/CORE_DEPENDENCY_MAP.md` — Bible 상태 갱신
- `reports/PHASE1C_BIBLE_NEXT_BOUNDARY_ANALYSIS.md` — 분석 기록
- `reports/PHASE1C_BIBLE_IMPORT_BATCH_REPORT.md`

## 변경 전/후 구조

```text
이전: core.import_items → license 검사 + passages upsert + RAG invalidation
이후: core.import_items → normalization/license 검사 → repositories.bible.persist_passage_batch → SQLite
```

## 호환성

- `import_items(items, db_path)` public signature와 반환 count 유지
- `passages` upsert SQL, `(translation, reference)` conflict update, RAG vector invalidation 유지
- SQLite schema/data, API URL/request/response/status 변경 없음
- Settings·Project·Doctrine·Sermon·RAG 검색·Grounding·Router 변경 없음

## 테스트

- 변경 전 관련 테스트: `49 passed in 10.18s`
- 변경 후 관련 테스트: `49 passed in 9.92s`
- 변경 후 전체 pytest: `212 passed in 22.15s`

## 순환 import

`app.repositories.bible`는 `app.core`/`app.main`/Provider/RAG service를 import하지 않는다. `core → repositories.bible` 단방향을 유지했다.

## 발견된 위험

- license 사전검사와 실제 upsert가 별도 DB 연결로 실행되므로, 극단적인 동시 license 변경 상황에서는 기존 단일 연결보다 검사 시점과 쓰기 시점 사이가 넓어진다. 일반 호출과 batch write atomicity는 유지되며, 동시성 정책 변경은 별도 설계 대상이다.
- `delete_bible_translation`은 파괴적·RAG 결합 작업이므로 아직 Core에 남아 있다.

## Rollback 방법

`import_items`에 기존 SQL upsert/invalidation 블록을 복원하고 `persist_passage_batch` import/함수를 제거하면 된다. DB rollback은 필요하지 않다.

## 다음 단계

이 단계만 완료하고 중단한다. 다음 후보(`delete_bible_translation` 또는 Bible 잔여 함수)는 파괴적 동작과 RAG 결합도 분석 및 별도 승인을 거친 뒤 진행한다.
