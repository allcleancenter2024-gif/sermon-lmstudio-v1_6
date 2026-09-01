# Phase 2E Grounding Dashboard 완료 보고

## 작업 전 Baseline

Git metadata가 없는 작업 디렉터리이며 제품 버전 후보는 `sermon-lmstudio-final-package-v40`이다. Grounding Validator/Audit과 Dashboard는 기본 비활성, 전체 pytest 기준선은 **212 passed** (`22.02s`)였다.

## 기존 UI 구조

Vanilla JS(`static/app.js`)와 기존 CSS(`static/v2.css`)를 사용하는 단일 설교 결과 화면이다. 기존 `auditBox`, 품질검사, Citation Mapping 영역을 유지했다.

## Grounding 데이터 흐름

생성 결과의 optional `grounding_audit` metadata를 기존 result state가 보유하고, Dashboard는 이를 읽기 전용으로 렌더링한다. Audit이 없으면 비활성/기록 없음 상태를 표시한다.

## Preflight 통합

기존 Preflight 계산과 response contract는 변경하지 않았다. Dashboard는 생성 결과 화면에 추가되며 Preflight 규칙을 변경하지 않는다.

## Generation Audit 통합

기존 `auditBox`를 유지하고, 별도 Grounding Summary 카드에서 grounded/partial/ungrounded/coverage를 표시한다. Generation Audit schema/DB는 변경하지 않았다.

## 결과 화면 통합

`templates/index.html`의 기존 결과 패널에 읽기 전용 `groundingDashboard` 영역을 추가했다. 생성/저장/Export 버튼과 workflow는 유지했다.

## Dashboard 구조

요약 카드 4개(근거 확인, 부분 확인, 확인 필요, 근거 연결률)와 접을 수 있는 상세 Claim 목록을 제공한다. 상세는 최대 10건만 렌더링한다.

## 상태 표현 정책

✓ 근거 확인, △ 부분 확인, ! 확인 필요를 텍스트와 함께 표시한다. Audit 미사용/기록 없음은 `설교문 근거 검증: 사용 안 함 또는 기록 없음`으로 표시한다.

## Coverage 표현 정책

`Grounding Coverage`는 검증 대상 Claim 중 grounded 비율로만 표시하며 정확도·진실도·신학적 정확도로 표현하지 않는다. not_applicable은 분모에서 제외된 Audit 결과를 사용한다.

## 변경 파일

- `app/main.py`
- `templates/index.html`
- `static/app.js`
- `static/v2.css`
- `reports/PHASE2E_GROUNDING_DASHBOARD_REPORT.md`

## API 영향

기존 URL/method/request/response 필드를 삭제하거나 변경하지 않았다. Dashboard는 optional `grounding_audit`가 존재할 때만 표시한다.

## DB 영향

DB schema, backup schema, 저장 데이터 변경 없음.

## RAG 영향

Semantic, Legacy/FTS5 Lexical, RRF, top_k, ranking 변경 없음. Dashboard 표시 시 재검색하지 않는다.

## Grounding Validator 영향

Validator 규칙과 Tier 정책 변경 없음. 생성 전 Validator와 생성 후 Audit을 UI에서 별도 영역으로 취급한다.

## Grounding Audit 영향

Audit 결과를 읽기 전용으로 표시한다. 자동 수정·삭제·재생성은 수행하지 않는다. Audit 오류가 생성 실패로 전파되지 않는다.

## LM Studio 영향

추가 LM Studio 호출 없음.

## 기존 Sermon 호환

과거 설교에 Grounding 결과가 없어도 본문·메타데이터·기존 검토/Export 흐름을 사용할 수 있다. Dashboard만 기록 없음 상태를 표시한다.

## 모바일 UI 결과

기존 responsive CSS breakpoint를 재사용하고 Grounding 통계 카드는 600px 이하에서 2열로 축소된다. 새 프레임워크는 추가하지 않았다.

## 브라우저 Smoke Test

자동 브라우저 도구를 사용한 실제 클릭 smoke test는 수행하지 않았다. 대신 HTML home 응답에 flag와 Dashboard DOM이 포함되는지 확인했다.

## Console Error 결과

정적 함수 문법 및 Python import/compile 검사는 통과했다. 실제 브라우저 Console 0건은 별도 수동 브라우저 실행이 필요한 항목으로 남겼다.

## 관련 테스트

기존 생성·Evidence·Preflight·Audit·Backup 회귀: **59 passed in 13.30s**. `home()` 응답에 Dashboard flag/DOM 존재 확인 통과.

## 전체 pytest 결과

**212 passed in 21.89s**, failed 0, error 0.

## 성능 영향

Audit 결과가 이미 응답에 있을 때만 DOM을 생성하며, UI 표시 시 RAG/DB 전체 scan/LM 호출을 하지 않는다. 상세 Claim은 최대 10건으로 제한한다.

## 발견된 문제

없음. Git status/branch는 repository metadata 부재로 확인할 수 없다. 실제 브라우저 smoke/console 검증은 미실행이다.

## 남은 위험

`GROUNDING_DASHBOARD_ENABLED` 기본값이 false이므로 운영에서 활성화하려면 환경변수 설정이 필요하다. 기존 저장 설교에는 Audit metadata가 없을 수 있으며, 이 경우 정상적으로 기록 없음으로 표시된다.

## Rollback 방법

`GROUNDING_DASHBOARD_ENABLED=false`로 유지하거나 Dashboard HTML/JS/CSS 변경을 제거하면 기존 화면으로 복귀한다. Validator/Audit 자체와 DB 데이터는 유지된다.

## 다음 권장 단계

이번 Phase 2E 범위에서 중단한다. 자동 수정, Web Grounding, Grounding Export Report, Router 분리는 별도 승인 후 진행한다.
