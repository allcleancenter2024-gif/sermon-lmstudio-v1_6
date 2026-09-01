# Phase 1C-5 Sermon Repository 완료 보고

## 작업 전 Baseline

- Git 저장소 메타데이터는 확인할 수 없는 작업 디렉터리였으며, 버전 후보는 `sermon-lmstudio-final-package-v40`이다.
- 전체 pytest 기준선: **212 passed** (`22.79s`).
- Sermon 관련 변경 전 회귀 기준선: **53 passed** (`13.19s`).

## 기존 Sermon 구조

`core.py`의 `save_sermon()`이 Project Repository에 있던 `persist_sermon_version()`을 직접 호출했다. 해당 함수에는 `sermons`, `sermon_versions`, `generation_audits` 테이블 보장, sermon/version 저장, eligible audit 연결 및 metadata 정리가 함께 포함되어 있었다.

## Sermon DB Table

기존 `sermons`, `sermon_versions`, `generation_audits` 테이블 정의와 컬럼, 제약조건을 그대로 유지했다. migration이나 기존 데이터 변환은 수행하지 않았다.

## 관련 Public Interface

`save_sermon(topic, content, metadata, sermon_id=None, db_path=DB_PATH)` 시그니처와 반환 dict(`sermon_id`, `version`, `created_at`, `audit_linked`)를 유지했다. Project 모듈의 기존 `persist_sermon_version` import 경로도 compatibility re-export로 유지했다.

## Sermon Generation과 Persistence 경계

이번 단계는 DB persistence만 대상으로 했다. 생성, outline, revision suggestion, Evidence/Preflight/Grounding, Export 및 API 조립은 이동하지 않았다.

## 이동한 함수/책임

- `app/repositories/sermon.py` 생성
- `persist_sermon_version()` 및 persistence table bootstrap을 Sermon Repository로 이동
- DB 읽기/쓰기와 audit 연결 로직을 새 Repository에서 수행

## 이동하지 않은 함수/책임

Project metadata/list/version 비교 및 dashboard 입력 조립은 `app/repositories/project.py`에 남겼다. Sermon 생성·분석 함수와 Bible, Doctrine, RAG, Router도 변경하지 않았다.

## core.py Compatibility Wrapper

`core.save_sermon()`은 기존 public facade로 남기고 내부 호출 대상만 `app.repositories.sermon.persist_sermon_version`으로 변경했다. 호출부의 대규모 변경은 없었다.

## 새 Repository 구조

`core.py → app.repositories.sermon.persist_sermon_version → SQLite`의 단방향 경로다. `app.repositories.sermon`은 `app.core`나 `app.main`을 import하지 않는다. Project 모듈은 기존 외부 호출 호환을 위해 Sermon 구현을 re-export한다.

## 변경 파일

- `app/repositories/sermon.py`
- `app/repositories/project.py`
- `app/core.py`
- `reports/CORE_DEPENDENCY_MAP.md`
- `reports/PHASE1C_SERMON_REPOSITORY_REPORT.md`

## SQLite Schema 영향

없음. `CREATE TABLE IF NOT EXISTS`의 기존 정의만 새 Repository에서 사용한다.

## 기존 Sermon DB 호환성

기존 sermon 및 version 데이터에 대해 동일한 SQL, version 계산, topic 기본값, metadata JSON 직렬화, audit 연결 조건을 유지한다.

## Project 관계 영향

Project와 Sermon의 기존 `sermon_id` 연결만 사용하며 Project schema나 dashboard 동작은 변경하지 않았다.

## Review/Audit 영향

기존 `generation_audits`의 eligible row 연결과 metadata cleanup 로직을 persistence 함수 안에서 그대로 유지했다. Audit state machine 자체는 이동하지 않았다.

## Evidence/Preflight 영향

코드 변경 없음. 관련 회귀 테스트 통과.

## Grounding 영향

코드 변경 없음. 관련 회귀 테스트 통과.

## LM Studio 영향

Provider 및 호출 URL 변경 없음.

## Export 영향

Export 경로와 응답 형식 변경 없음.

## API 영향

API URL, request/response 형식 변경 없음.

## 성능 영향

동일한 SQL과 transaction 경계를 사용하므로 의도된 동작·쿼리 수 변화는 없다.

## 순환 Import 검사

`app.repositories.sermon`에서 `app.core`/`app.main` import가 없음을 확인했다. `core → sermon` 단방향 import이며, Project compatibility re-export도 역방향 import를 만들지 않는다.

## 관련 테스트 결과

변경 전후 Sermon 관련 기준 테스트와 확장 회귀를 순차 실행했으며 모두 통과했다: `34 + 35 + 40 + 35 + 8 + 18 + 39 + 6` passed (각 그룹 exit 0).

## 전체 pytest 결과

**212 passed in 22.12s** (`pytest -q`, exit 0).

## 추가 테스트

별도 테스트 파일 추가 없이 기존 테스트 세트를 사용했다.

## 발견된 문제

Project 모듈에는 과거 구현이 `_legacy_persist_sermon_version`이라는 private 이름으로 남아 있고, 공개 이름은 새 Sermon Repository 구현을 re-export한다. 런타임 호출에는 사용되지 않지만 후속 정리 시 제거 대상으로 기록했다. 작업 디렉터리는 Git metadata가 없어 branch/status 기반 diff 확인은 불가했다.

## 남은 위험

Project Repository에 `list_sermons`, `sermon_versions`, `compare_sermon_versions`, dashboard 입력 조립이 남아 있어 Project/Sermon persistence 경계가 완전히 정리된 것은 아니다. 또한 audit 연결은 Sermon persistence와 같은 transaction에 의존한다.

## Rollback 방법

`core.save_sermon()` 호출 대상을 기존 Project 구현으로 되돌리고 Sermon import 및 `app/repositories/sermon.py`를 제거하면 된다. Git metadata가 없으므로 롤백 전 파일 백업 또는 본 보고서의 변경 목록을 기준으로 수동 복원한다. DB migration을 하지 않았으므로 데이터 rollback은 필요하지 않다.

## 다음 권장 단계

이번 지시서 범위는 여기서 중단한다. 다음 단계 진행 전 별도 승인 후 Sermon Service 분리 경계를 분석한다. Doctrine/Bible/RAG/Router 분리는 자동으로 시작하지 않는다.
