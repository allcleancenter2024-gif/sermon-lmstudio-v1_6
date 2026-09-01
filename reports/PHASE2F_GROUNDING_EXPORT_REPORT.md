# Phase 2F Grounding Report Export 완료 보고

## 작업 전 Baseline

Git metadata가 없는 작업 디렉터리이며 제품 버전 후보는 `sermon-lmstudio-final-package-v40`이다. Grounding Dashboard/Audit은 기본 비활성이고 전체 pytest 기준선은 **212 passed** (`22.02s`)였다.

## 기존 Export 구조

기존 `app.exporters.py`와 `/api/export/{markdown,html,word,pdf}`가 설교 본문 Export를 담당한다. 이 경로는 변경하지 않았다.

## Grounding Report 데이터 원본

이미 계산된 `meta.grounding_audit`, `meta.sources`, 설교 metadata만 사용한다. Export 시 RAG, Validator, Audit, DB 재조회나 LM Studio 호출을 수행하지 않는다.

## 공통 Report View Model

`app.exporters_grounding.GroundingReportData`가 제목, 본문, 모델, Audit summary, Evidence 목록을 공통으로 보유하고 HTML/Markdown renderer가 이를 공유한다.

## HTML Export 구조

독립 UTF-8 standalone HTML로 기본정보, 근거 요약, 검토 필요 Claim, 전체 Claim, Evidence preview, 목회자 메모, 면책 문구를 표시한다. inline CSS와 `@media print`를 포함한다.

## Markdown Export 구조

동일 View Model을 Markdown heading/list 구조로 렌더링한다. HTML과 Coverage, counts, reference, Evidence 핵심 값이 동일하다.

## 변경 파일

- `app/exporters_grounding.py`
- `app/main.py`
- `templates/index.html`
- `static/app.js`
- `reports/PHASE2F_GROUNDING_EXPORT_REPORT.md`

## UI 연결

Grounding Dashboard가 활성화되고 Report Export flag가 활성화된 경우 기존 결과 화면에 `근거 보고서 HTML`, `근거 보고서 MD` 버튼을 표시한다. Grounding 결과가 없으면 저장을 시도하지 않고 안내한다.

## API 연결

`POST /api/export/grounding`을 추가했다. `format=html|markdown`을 지원하며 기존 설교 Export endpoint는 변경하지 않았다. 기본 `GROUNDING_REPORT_EXPORT_ENABLED=false`일 때 404로 비활성 상태를 명시한다.

## 파일 저장 위치

기존 `EXPORTS_DIR` 정책을 사용한다. 새로운 절대 경로를 하드코딩하지 않았다.

## 파일명 안전 처리

`grounding_report_<제목>_<timestamp>.<html|md>` 형식이며 Windows 금지문자를 `_`로 치환하고 제목을 80자 이내로 제한한다. 기존 Export를 덮어쓰지 않는다.

## HTML Escape 처리

제목, metadata, Claim reason, Evidence source/reference/preview를 `html.escape`로 처리한다. 사용자 입력 HTML/Script가 실행되지 않도록 했다.

## Grounding Validator 영향

Validator 규칙과 Tier 정책 변경 없음.

## Grounding Audit 영향

Audit 결과를 재계산하지 않고 전달된 결과만 렌더링한다. Audit이 없으면 기록 없음으로 표시한다.

## RAG 영향

검색·FTS5·RRF·embedding 호출 없음.

## LM Studio 영향

추가 호출 0회.

## 기존 Sermon Export 영향

기존 Markdown/HTML/DOCX/PDF endpoint와 renderer 코드를 수정하지 않았다.

## DB 영향

DB schema 및 데이터 변경 없음.

## 성능

인메모리 View Model 변환과 문자열 렌더링만 수행하며 외부 호출/DB 조회가 없다. 생성 Pipeline latency에는 영향이 없다.

## 관련 테스트 결과

Grounding Export renderer/escape/filename smoke와 기존 생성·Evidence·Preflight·Backup 회귀: **59 passed in 21.68s**.

## 전체 pytest 결과

**212 passed in 31.10s**, failed 0, error 0.

## Browser Smoke Test

실제 브라우저 클릭 및 파일 다운로드 smoke test는 수행하지 않았다. HTML home 응답의 Dashboard/Export flag 및 DOM 연결과 renderer 생성 검사를 수행했다.

## 발견된 문제

없음. Git status/branch는 repository metadata 부재로 확인할 수 없다. 실제 브라우저 Console 검증은 별도 수동 확인이 필요하다.

## 남은 위험

기본 flag가 false이므로 운영에서 기능을 사용하려면 `GROUNDING_DASHBOARD_ENABLED`와 `GROUNDING_REPORT_EXPORT_ENABLED`를 명시적으로 활성화해야 한다. 과거 설교에 Audit metadata가 없으면 보고서 생성이 차단된다.

## Rollback 방법

`GROUNDING_REPORT_EXPORT_ENABLED=false`로 비활성화하고 Dashboard 보고서 버튼/endpoint 연결을 제거하면 된다. 기존 Sermon Export, Grounding Validator/Audit, DB 데이터는 유지된다.

## 다음 권장 단계

이번 Phase 2F 범위에서 중단한다. Grounding PDF, Web Grounding, 자동 보강/수정, Router 전체 분리는 별도 승인 후 진행한다.
