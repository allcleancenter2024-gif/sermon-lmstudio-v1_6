# Phase 3B Web Grounding 완료 보고

## 작업 전 Baseline

- 제품 버전: Sermon LM Studio V40.9.1
- Git: 현재 디렉터리는 Git working tree가 아니어서 status/branch를 조회할 수 없음
- 프로젝트 `.venv`: 기존 전체 pytest **212 passed**
- 시스템 Python은 python-docx 누락으로 baseline에 사용하지 않음

## 기존 Grounding 구조

EvidenceCandidate → Grounding Validator → optional Grounding Audit/Report 구조를 유지했다. Validator에는 기존부터 `web → Tier D/weak` 규칙이 있어 이를 재사용했다.

## Web Grounding 목표

외부 사실이 명시적으로 요청된 경우에만 검색하고, 결과를 runtime `EvidenceCandidate(source_type="web")`로 전달한다. Scripture·원어·Doctrine의 대체나 자동 승격은 하지 않는다.

## 선택한 Search Provider

단일 generic HTTP JSON Provider(`HttpJsonWebSearchProvider`)를 추가했다. endpoint와 API key는 환경변수로만 받으며, 미설정 시 네트워크 요청을 하지 않는다.

## Provider Adapter 구조

`app/providers/web/base.py`의 `WebSearchProvider` Protocol, `HttpJsonWebSearchProvider`, `NullWebSearchProvider`, `WebEvidenceAdapter`로 구성했다. `app.providers.web`에서 공개한다.

## 변경 파일

- `app/providers/web/__init__.py`
- `app/providers/web/base.py`
- `app/main.py` (선택 필드와 조건부 연결)
- `app/services/sermon_service.py` (runtime web evidence 전달)
- `tests/test_v45_web_grounding.py`
- `reports/PHASE3B_WEB_GROUNDING_REPORT.md`

## Feature Flag

`WEB_GROUNDING_ENABLED` 기본값은 `false`다. 요청의 `web_grounding`도 기본 `false`이며 두 조건이 모두 true일 때만 동작한다.

## API Key 관리

`WEB_SEARCH_API_KEY` 환경변수에서만 읽고 응답·로그에 출력하지 않는다. 소스/HTML/JavaScript에는 키를 넣지 않았다.

## Search Query 정책

topic/details만 정규화해 최대 240자로 만들며, 전체 설교 초안·비공개 메모를 전송하지 않는다. `latest/current/recent`, 최근·현재·통계·뉴스·외부 연구 등 명시적 키워드가 있을 때만 검색한다.

## 검색 호출 제한

한 생성당 최대 1회 adapter 호출, 결과 최대 5건이다.

## Timeout 정책

HTTP Provider timeout은 5~15초 범위(기본 10초)로 제한한다.

## Web Evidence 모델

제목·URL·domain·snippet·published_at·retrieved_at·provider metadata를 보존한다. 게시일을 추정하지 않으며 URL은 `http/https`만 허용한다.

## Tier D 정책

모든 Web Evidence는 `source_type=web` 및 Validator의 Tier D/weak로 유지된다. Tier A/B/C로 승격하지 않는다.

## Evidence Merge 방식

내부 passages/word/doctrine evidence와 별도 web evidence를 prompt 및 audit packet에 추가하며 source identity와 metadata를 보존한다. 기존 response에는 flag가 실제 활성화된 경우에만 `web_grounding` metadata가 추가된다.

## Grounding Validator 영향

기존 `web → Tier D/weak` 규칙을 그대로 사용했다. A/B/C 정책은 변경하지 않았다.

## Grounding Audit 영향

기존 audit packet에 web evidence를 optional로 추가했다. external_fact/statistical/historical claim의 source id 추적이 가능하며 별도 Audit 시스템은 만들지 않았다.

## Preflight 영향

변경하지 않았다. Web 실패가 generation readiness를 변경하지 않는다.

## Sermon Generation 영향

OFF 또는 일반 성경 요청은 기존 workflow와 동일하다. ON이고 외부 사실 키워드가 있을 때만 검색하며 실패 시 빈 evidence로 기존 생성을 계속한다.

## Grounding Dashboard 영향

기존 대시보드 UI는 변경하지 않았다. runtime metadata는 후속 최소 UI 연결에 사용할 수 있다.

## Grounding Report 영향

기존 exporter 구조는 변경하지 않았다. Web evidence 표시용 optional metadata를 유지하며 일반 Sermon export에는 강제 삽입하지 않는다.

## RAG 영향

FTS5/RRF 및 내부 RAG 알고리즘은 변경하지 않았다.

## LM Studio 영향

LM Studio Provider는 변경하지 않았다.

## DB 영향

새 테이블·migration·schema 변경이 없다. Web Evidence는 runtime에서만 처리된다.

## Offline 동작

기본 OFF이며 endpoint 미설정/네트워크 단절 시 빈 결과와 fallback metadata를 반환한다. 내부 local pipeline은 계속 동작한다.

## Provider 장애 Fallback

timeout, 401/403, 429, 5xx, URL/JSON 오류를 adapter가 포착해 generation 예외로 전파하지 않는다.

## API Key 보안 검사

키를 source/HTML/응답/log에 기록하지 않는 구조를 확인했다.

## 검색 성능

Provider latency는 adapter metadata의 `elapsed_ms`로 기록한다. 실제 외부 endpoint는 설정되지 않아 네트워크 성능 측정은 수행하지 않았다.

## Provider 호출 횟수

생성당 최대 1회, 최대 5 결과.

## 관련 테스트

Web adapter/disabled/fallback/Tier-D/URL dedupe 테스트 및 기존 Evidence·Preflight·Audit·Backup/NotebookLM 회귀: **32 passed**.

## 전체 pytest 결과

`.venv\Scripts\python.exe -m pytest -q`: **216 passed**, failed=0, error=0.

## 발견된 문제

Git metadata가 없어 branch/status는 확인할 수 없다. 실제 Provider endpoint가 없는 환경이므로 live search는 검증하지 않았다.

## 남은 위험

Provider별 응답 schema·rate limit semantics는 실제 endpoint 연동 시 추가 contract test가 필요하다. Web Evidence를 Dashboard/Report에 시각적으로 표시하는 작업은 후속 승인 범위다.

## Rollback 방법

1. `WEB_GROUNDING_ENABLED=false` 유지/복원
2. 요청 `web_grounding`을 생략하거나 false로 전환
3. 필요 시 `app/providers/web` 및 두 연결부를 제거
4. 내부 Evidence pipeline과 DB는 그대로 유지
5. 전체 pytest 재실행

DB rollback은 필요하지 않다.

## 다음 권장 단계

실제 Provider를 활성화하기 전 endpoint schema와 운영 rate-limit을 승인·검증한다. 이번 단계에서는 기본 활성화, 두 번째 Provider, 자동 보강/재생성, Router·UI 대규모 변경을 수행하지 않고 중단한다.
