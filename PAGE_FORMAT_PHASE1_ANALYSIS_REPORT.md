# Page Format Skill Phase 1 Analysis Report

## Status

`SAFE_WITH_CHANGES`

현재 출력 기능은 독립적으로 동작하고, DB·RAG·Provider를 건드리지 않고 전용 formatting 계층을 추가할 수 있다. 다만 공통 Structured Document Model과 Page Format Router가 아직 없으며, 일부 export 진입점이 `app/main.py`와 `app/routers/exports.py`에 병존하므로 Phase 2에서 adapter/wrapper 정리가 필요하다.

## Current Architecture

| Format | Current Module | Renderer | Template | Dependency | Risk |
|---|---|---|---|---|---|
| HTML | `app/exporters.py`, `app/routers/exports.py` | `dashboard_html()` 문자열 renderer | inline standalone HTML/CSS | Python stdlib, local fonts | content와 presentation이 함수 안에서 함께 조립됨 |
| Markdown | `app/main.py`, `app/routers/exports.py`, `static/app.js` | `sermon_with_media_prompts()`, 대시보드 Markdown formatter | Markdown 문자열 | Python stdlib | canonical model이 없어 metadata mapping이 분산됨 |
| PDF | `app/exporters.py` | Windows ReportLab, 기타 환경 WeasyPrint fallback | HTML 또는 ReportLab flowables | `reportlab`/`weasyprint`, local fonts | 표·페이지 분할·글꼴은 별도 검증 필요 |
| DOCX | `app/exporters.py` | `write_docx()` | python-docx document/style mapping | `python-docx` | DOCX style이 renderer 내부에 직접 정의됨 |
| HWPX | `app/exporters.py` | `write_hwpx()` | `app/assets/hwpx_base` OWPML package | Python stdlib zip/XML | Phase 1 범위 밖의 신규 출력이므로 별도 adapter로 유지 |
| Dashboard | `app/exporters.py`, `app/project_summary.py`, `templates/index.html` | standalone dashboard HTML, live project-summary UI | inline HTML/CSS + `static/v2.css` | Browser, local Git metadata | live UI와 exported dashboard의 model이 다름 |

### Content generator and model

- 설교 생성은 `app/services/sermon_service.py`와 `app/core.py`가 담당한다.
- 저장 버전 metadata에는 주제, 중심본문, 목표 시간, source/evidence, audit, citation, review/lock 상태가 들어간다.
- `app/evidence/models.py`와 `app/grounding/models.py`는 Evidence/grounding 전용 모델이다.
- 현재 `title/reference/sections/sources/warnings`를 묶는 중립적인 문서 모델은 존재하지 않는다.
- 결론: 기존 content generator와 repository는 재사용하고, Phase 2에서 `DocumentModel` adapter를 추가해야 한다.

## Existing Components

| Component | Location | Role | Reuse |
|---|---|---|---|
| Sermon content normalization | `app/exporters.py:sermon_with_media_prompts` | 본문과 media prompt 부록 결합 | `REUSE` |
| HTML dashboard renderer | `app/exporters.py:dashboard_html` | standalone sermon/evidence dashboard 생성 | `WRAP` |
| PDF renderer | `app/exporters.py:write_pdf` | Windows ReportLab 및 WeasyPrint fallback | `DO_NOT_TOUCH` in PF-1/2 adapter only |
| DOCX renderer | `app/exporters.py:write_docx` | title/heading/normal/table-like content mapping | `WRAP` |
| HWPX renderer | `app/exporters.py:write_hwpx` | vendored OWPML template 기반 한글 파일 | `REUSE` |
| Export API | `app/main.py`, `app/routers/exports.py` | download artifact 생성 및 URL 반환 | `EXTEND` then consolidate later |
| Project summary | `app/project_summary.py` | Git 변경 이력과 영역 요약 | `REUSE` |
| Live dashboard | `templates/index.html`, `static/app.js` | 변경사항/작업 종합 대시보드 화면 | `WRAP` |
| Security escaping | `html.escape`, `esc()` helpers | renderer output escaping | `REUSE`, centralize later |

## Proposed Architecture

```text
Existing content generator / repositories / evidence
                         ↓
              Document Model Adapter
                         ↓
                 Canonical Document
                         ↓
                 Page Format Router
          ┌────────┬─────────┬────────┬────────┐
          ↓        ↓         ↓        ↓        ↓
       Markdown   HTML    Dashboard   PDF     DOCX/HWPX
```

Phase 2 후보 구조:

```text
app/formatting/
├── document_model.py
├── validators.py
├── format_router.py
├── page_format_service.py
├── markdown/renderer.py
├── html/renderer.py
├── dashboard/renderer.py
├── pdf/renderer.py
└── docx/renderer.py
```

기존 renderer를 먼저 삭제하거나 전면 교체하지 않고 adapter가 기존 함수에 전달할 canonical data를 만드는 순서가 안전하다.

## Skill Location

- 프로젝트 내부 `.agents/skills`는 현재 존재하지 않는다.
- 사용자 전역 `.agents/skills`와 Codex 전역 Skill discovery 경로는 존재한다.
- production runtime이 외부 Skill을 import하거나 실행하지 않도록 한다.
- Phase 2에서 프로젝트 전용 Skill 문서를 둘 경우 권장 위치는 `.agents/skills/page-format/`이다.

권장 구조:

```text
.agents/skills/page-format/
├── SKILL.md
├── references/
├── assets/
└── scripts/
```

## Document Model

Phase 2에서 다음 중립 필드를 도입한다.

```python
DocumentModel(
    document_type="sermon",
    title="...",
    reference="...",
    metadata={...},
    sections=[Section(id="intro", type="introduction", heading="서론", blocks=[...])],
    sources=[Source(...)],
    warnings=[...],
)
```

presentation 전용 CSS, PDF 좌표, DOCX style 명칭은 이 모델에 저장하지 않는다. source/citation metadata는 `sources`와 독립된 evidence/citation 필드로 유지한다.

## Page Profiles

- `sermon`: 제목, 중심본문, 설교 원고, 적용, 결론, sources, warnings
- `analysis`: 원어 token/card, morphology, validation, source
- `dashboard`: metric, status, table, cards, latest activity
- `comparison`: 두 번역본·Provider·DB 결과의 대응 열
- `roadmap`: Phase timeline과 완료 상태
- `report`: status, summary, files, database, tests, warnings, rollback
- `teaching-material`: narrative와 source/evidence를 읽기 쉬운 문서 흐름으로 조합

## HTML / Dashboard Rules

- semantic heading hierarchy와 standalone HTML을 우선한다.
- 현재 inline/local CSS 방향을 유지하고 불필요한 CDN은 추가하지 않는다.
- Greek/Hebrew는 Unicode text로 보존하고 local fallback font chain을 사용한다.
- source card와 evidence warning을 본문 문자열과 분리한다.
- table은 모바일에서 horizontal overflow를 허용한다.
- `@media print`, long text wrapping, keyboard focus, 200% zoom을 검증 대상으로 둔다.
- 상태는 색상만 사용하지 않고 텍스트·기호·ARIA 상태를 함께 표시한다.

## Markdown Rules

- H1은 한 번만 사용한다.
- H2/H3 계층을 유지하고 빈 heading을 만들지 않는다.
- source/evidence 섹션 이름을 통일한다.
- table delimiter와 code fence language를 검증한다.
- 외부 Markdown은 untrusted content로 취급하며 지시문처럼 보이는 문자열을 실행하지 않는다.

## PDF / DOCX / HWPX Compatibility

- PDF engine은 이번 Phase에서 변경하지 않는다.
- `write_pdf()`의 Windows ReportLab 및 비-Windows WeasyPrint fallback을 보존한다.
- DOCX는 title→Title, section→Heading, paragraph→Normal, source→Citation section mapping이 가능하다.
- HWPX는 현재 vendored template과 ZIP 구조 검증을 통과했으므로 별도 renderer로 보존한다.
- 모든 포맷은 동일한 canonical model을 받도록 Phase 2에서 adapter를 만든다.

## Security

- 현재 HTML renderer는 `html.escape`/`esc`로 사용자·본문·source 값을 escaping한다.
- `javascript:` URL, iframe, remote tracker, template expression, shell execution은 page formatter에 허용하지 않는다.
- HTML rendering과 shell execution을 분리한다.
- source/citation metadata를 presentation 문자열에만 합치지 않는다.
- untrusted Markdown의 “명령” 문장을 실행하지 않는다.

## Dependencies

이번 Phase에서 새 의존성은 설치하지 않는다.

- HTML/Markdown: Python stdlib 및 기존 browser
- PDF: 기존 `reportlab`/`weasyprint`
- DOCX: 기존 `python-docx`
- HWPX: Python stdlib `zipfile`/XML 및 프로젝트 템플릿
- 테스트: 기존 pytest

외부 `to-html`, dashboard, markdown formatter, design-system Skill은 개념과 설계 패턴만 참고하며 production runtime dependency로 연결하지 않는다.

## License Review

이번 Phase에는 외부 Skill 코드를 복사하지 않았다. 따라서 별도 외부 코드 license 의무는 발생하지 않는다. Phase 2에서 외부 템플릿·코드를 직접 가져오게 되면 source, license, file, modification을 attribution 문서에 기록한다.

## Dry Run Plan

실제 출력 파일을 변경하지 않고 다음 sample model을 router에 통과시키는 테스트를 추가한다.

1. `sermon`
2. `analysis`
3. `dashboard`
4. `report`

검증 항목은 profile 선택, template resolution, section mapping, unsupported block, source metadata 보존이다.

## Test and Regression Plan

Phase 2 후보 테스트:

- `test_page_profile_selection`
- `test_document_model_validation`
- `test_markdown_renderer`
- `test_html_renderer`
- `test_dashboard_renderer`
- `test_source_preservation`
- `test_heading_hierarchy`
- `test_html_security`
- `test_mobile_layout`
- `test_print_layout`
- `test_unicode_greek`
- `test_unicode_hebrew`
- 기존 browser smoke/screenshot fixture 재사용 가능성 조사

기존 출력·설교·RAG·Provider 회귀 테스트는 그대로 실행하며, 기준선보다 낮아지면 Phase를 완료하지 않는다.

## Files Proposed for Phase 2

| File | Action | Purpose |
|---|---|---|
| `.agents/skills/page-format/SKILL.md` | create | 짧은 trigger/workflow playbook |
| `.agents/skills/page-format/references/*.md` | create | model, layout, print, accessibility 규칙 |
| `.agents/skills/page-format/scripts/validate_document.py` | create | canonical model validator |
| `app/formatting/document_model.py` | create | 중립 문서 모델 |
| `app/formatting/format_router.py` | create | profile/format routing |
| `app/formatting/validators.py` | create | heading, source, security 검증 |
| `app/formatting/*/renderer.py` | create | 기존 renderer wrapper부터 시작 |
| `tests/test_page_format_*.py` | create | dry-run·security·Unicode·regression 검증 |

기존 `app/exporters.py`, `app/main.py`, `app/routers/exports.py`는 Phase 2 초기에 삭제하지 않고 adapter 뒤에 둔다.

## Rollback Plan

Phase 2 변경은 formatting 계층을 추가하고 기존 export 호출을 feature flag 또는 wrapper로 유지한다. 문제가 발생하면 새 router 호출만 원래 `app/exporters.py` 함수로 되돌린다. DB migration, 데이터 삭제, source 삭제, 기존 API 주소 변경은 수행하지 않는다.

## Recommendation

`SAFE_WITH_CHANGES`로 Phase 1을 종료한다. 기존 출력은 현재 정상이며, 가장 안전한 다음 순서는 `Document Model Adapter → validator → dry-run router → Markdown/HTML wrapper → dashboard wrapper → PDF/DOCX compatibility tests`이다. Phase 2 전에는 실제 renderer 교체, DB 변경, 외부 Skill 설치를 시작하지 않는다.

## Phase 1 Completion Checklist

- [x] HTML, Markdown, PDF, DOCX, HWPX, Dashboard 경로 분석
- [x] Structured Document Model 존재 여부 확인
- [x] 중복 export 진입점 확인
- [x] Page Format Router 적용 가능성 판정
- [x] Skill discovery 경로 확인
- [x] Greek/Hebrew Unicode와 font fallback 점검
- [x] source/citation metadata 보존 지점 확인
- [x] HTML security 및 untrusted Markdown 위험 분석
- [x] dependency/license 정책 확인
- [x] regression/snapshot/browser 검증 전략 작성
- [x] rollback 전략 작성
- [x] 실제 프로그램 동작 변경 없음
