# Page Format Skill Phase PF-3 Quality Report

## Status

`PASS_WITH_WARNINGS`

PF-2의 `PASS_WITH_WARNINGS` 전제에 따라 품질 강화 계층을 추가했다. Golden Sample, structural/security/accessibility gate, Unicode/source integrity, PDF/DOCX smoke, quality score, rollback 검증을 완료했다. 연결된 브라우저 screenshot harness가 없어 visual pixel regression과 수동 viewport spot check는 보류 상태다.

## Golden Samples

| Profile | Result | Baseline |
|---|---|---|
| sermon | PASS | `tests/page_format/golden/sermon` v1 |
| greek-analysis | PASS | `tests/page_format/golden/greek-analysis` v1 |
| dashboard | PASS | `tests/page_format/golden/dashboard` v1 |
| comparison | PASS | `tests/page_format/golden/comparison` v1 |
| roadmap | PASS | `tests/page_format/golden/roadmap` v1 |
| report | PASS | `tests/page_format/golden/report` v1 |
| teaching-material | PASS | `tests/page_format/golden/teaching-material` v1 |

Golden baseline은 테스트 실패에 따라 자동 갱신하지 않았다. 각 profile에 input과 승인 metadata를 보관하고, sermon에는 Markdown/HTML expected snapshot을 추가했다.

## Visual Regression

| Profile | Desktop | Tablet | Mobile |
|---|---|---|---|
| sermon | 보류 | 보류 | 보류 |
| dashboard | 보류 | 보류 | 보류 |
| comparison | 보류 | 보류 | 보류 |
| report | 보류 | 보류 | 보류 |

Playwright dependency와 연결된 Chrome tab이 현재 환경에 없어 실제 screenshot 비교를 수행하지 않았다. 따라서 baseline을 자동 승인하지 않았으며, PF-4 이전에 1440x1000, 1024x768, 390x844로 실행해야 한다.

## Accessibility

- Critical: 0
- Major: 0 (자동 검사 범위)
- Minor: 수동 keyboard/focus/contrast/200% zoom spot check 필요
- 자동 gate: heading hierarchy, table header 조건, status 텍스트 조건, semantic HTML을 검사

## HTML Validation

`DOCTYPE`, `html lang`, UTF-8 charset, viewport, 단일 H1, heading level, duplicate ID, unsafe script, `javascript:` URL, inline event handler를 검사하며 샘플은 `VALID`이다.

## Unicode

- Greek: `ἀλήθεια`, `λόγος`, `πιστεύω`, `ἀγαπάω` 보존 검사 지원
- Hebrew: `שָׁלוֹם`, `אֱלֹהִים` 보존 검사 지원
- replacement character `�` 검출 시 critical failure
- 원어를 이미지로 대체하지 않음

## Source Integrity

Document Model의 source ID, reference, provider가 Markdown/HTML 출력에 보존되는지 검사한다. source가 렌더 결과에서 사라지면 quality score와 release gate에서 critical failure로 처리한다. PDF/DOCX는 기존 exporter smoke에서 핵심 문서 구조와 source 입력 경로를 확인한다.

## PDF

- 실제 가상환경 smoke: PASS
- 생성 파일: 정상 PDF signature
- 페이지 수: 2
- 기존 ReportLab exporter 유지
- A4/기존 글꼴·표·source renderer 변경 없음
- 긴 문서 페이지 분할과 추출 텍스트 세부 비교는 PF-4 후보

## DOCX

- 실제 가상환경 smoke: PASS
- `word/document.xml` 존재
- `w:document`, `w:body` 구조 확인
- 기존 python-docx exporter 유지
- 제목·본문·Unicode 입력 경로 확인
- 세부 style/pagination 시각 검사는 브라우저와 별도로 추가 필요

## Security

- script injection: PASS
- `javascript:` URL: validator 탐지
- inline handler: validator 탐지
- iframe/tracker/CDN/remote font: 추가하지 않음
- untrusted Markdown instruction: 실행하지 않고 텍스트로 처리

## Quality Score

현재 품질 score는 structure 20, content 20, source 20, accessibility 15, visual 15, export 10의 100점 모델을 사용한다. critical failure가 있으면 점수와 관계없이 `FAIL`이다. 정상 HTML sermon sample은 critical failure 없이 100점으로 계산된다.

## Performance

| Metric | PF-2 | PF-3 | Delta |
|---|---:|---:|---:|
| Markdown render | 미측정 | 단위 테스트 통과 | baseline 추가 필요 |
| HTML render | 미측정 | 단위 테스트 통과 | baseline 추가 필요 |
| Dashboard render | 미측정 | 단위 테스트 통과 | baseline 추가 필요 |
| PDF export | 미측정 | 2페이지 smoke 통과 | representative benchmark 필요 |
| DOCX export | 미측정 | package smoke 통과 | representative benchmark 필요 |

절대 시간이 매우 짧은 renderer의 퍼센트 비교를 임의로 만들지 않았으며, PF-4에서 긴 설교문 대표 fixture로 측정한다. 신규 renderer는 LLM을 호출하지 않는다.

## CI

현재 별도 CI workflow 파일은 확인되지 않았다. 로컬 표준 전체 테스트를 release gate로 실행했고, visual job은 브라우저 harness 연결 후 별도 job으로 분리하는 것이 적절하다.

## Rollback

- Feature flag: `PAGE_FORMAT_V2=false`
- 검증: 환경변수 미설정 시 legacy 경로, true 시 신규 adapter/router 경로 선택
- 기존 renderer 삭제 없음
- rollback 시 DB, source, 기존 API 응답 형식 변경 없음

## Tests

- 신규 Page Format 품질 테스트: `12 passed`
- 전체 regression: `278 passed`
- Python compileall: PASS
- HTML validator: PASS
- Document validator: PASS
- PDF smoke: `VALID PDF pages=2`
- DOCX smoke: `VALID DOCX`
- `git diff --check`: PASS

## Files Changed

| File | Action | Purpose |
|---|---|---|
| `app/formatting/quality.py` | create | HTML, Markdown, accessibility, Unicode, source, quality score gate |
| `.agents/skills/page-format/SKILL.md` | extend | PF-3 quality gate 및 progressive disclosure 연결 |
| `.agents/skills/page-format/references/` | create | quality, visual, PDF, DOCX, golden 규칙 |
| `.agents/skills/page-format/scripts/export_smoke.py` | create | PDF/DOCX package smoke |
| `tests/page_format/golden/` | create | 7 profile golden fixtures 및 metadata |
| `tests/test_page_format_quality.py` | create | quality/security/accessibility/source regression |
| `app/formatting/renderers/` | extend | source provenance 표시 보강 |
| `app/formatting/profiles.py` | extend | `greek-analysis` profile alias |

## External References / License

외부 코드·템플릿을 복사하지 않았다. 외부 Skill은 구조와 검증 개념만 참고했으며 production runtime dependency로 설치하지 않았다. 추가 dependency 문제도 없었다.

## Remaining Risks

- 실제 Chrome screenshot/console/mobile visual regression은 브라우저 연결 후 수행 필요
- PDF/DOCX 긴 문서 pagination과 글꼴별 glyph 검증 확대 필요
- 별도 CI workflow 연결 전까지는 로컬 전체 테스트가 release gate

## Recommendation

`PASS_WITH_WARNINGS`로 PF-3를 종료한다. 다음 PF-4에서는 브라우저 visual harness를 연결한 뒤 Golden Sample screenshot을 명시적으로 검토하고, 긴 문서 PDF/DOCX 성능·페이지 분할 benchmark를 추가한다. `PAGE_FORMAT_V2` 기본값은 계속 `false`로 유지한다.
