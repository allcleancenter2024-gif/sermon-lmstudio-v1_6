# PAGE_FORMAT_SKILL_INTEGRATION_PHASE2.md
# Codex 작업지시서 — Page Format Skill 통합 Phase PF-2
# 실제 구현 · 테스트 · 회귀검사

## 0. 목적

Phase PF-1 분석 결과가 `SAFE` 또는 `SAFE_WITH_CHANGES`일 때만 실행한다.

목표는 기존 프로그램의 콘텐츠 생성 로직을 건드리지 않고,
재사용 가능한 `page-format` Skill과 내부 formatting 계층을 실제 구현하는 것이다.

최종 흐름:

```text
Content Generator
        ↓
Structured Document Model
        ↓
Document Model Adapter
        ↓
Page Format Router
 ┌────────┼─────────┬──────────┬─────────┐
 ↓        ↓         ↓          ↓
Markdown  HTML   Dashboard   PDF Adapter
                                   ↓
                              DOCX Adapter
```

---

# 1. 구현 원칙

반드시 지킨다.

1. 기존 설교/RAG/Bible/Provider 생성 로직은 변경하지 않는다.
2. 기존 출력 기능은 즉시 삭제하지 않는다.
3. 기존 renderer가 있으면 `REUSE → WRAP → EXTEND` 순서로 우선한다.
4. 새 renderer는 content generator와 직접 결합하지 않는다.
5. 모든 출력은 동일한 Document Model을 입력으로 사용한다.
6. source/citation metadata가 렌더링 과정에서 사라지지 않아야 한다.
7. HTML은 standalone을 기본으로 한다.
8. 불필요한 외부 CDN, remote font, remote tracker를 추가하지 않는다.
9. HTML 내 script는 기본적으로 금지한다.
10. Dashboard에도 무거운 JS frontend framework를 새로 추가하지 않는다.
11. Greek/Hebrew Unicode를 보존한다.
12. Phase 2 구현 전후 전체 regression test를 비교한다.

---

# 2. Agent Skills 구조

Agent Skills 공개 표준에 맞춰 다음 구조를 우선한다.

```text
.agents/
└── skills/
    └── page-format/
        ├── SKILL.md
        ├── references/
        │   ├── document-model.md
        │   ├── html-layout.md
        │   ├── dashboard-layout.md
        │   ├── markdown-rules.md
        │   ├── accessibility.md
        │   ├── print-rules.md
        │   └── security.md
        ├── assets/
        │   ├── report-template.html
        │   ├── dashboard-template.html
        │   └── print.css
        └── scripts/
            ├── validate_document.py
            ├── validate_html.py
            └── snapshot_check.py
```

실제 Codex/Agent 환경의 Skill discovery path가 다르면 그 경로를 우선한다.

---

# 3. SKILL.md 작성 원칙

`SKILL.md`는 trigger + workflow + guardrail 중심으로 짧게 작성한다.

상세한 HTML/CSS 규칙이나 긴 예시는 `references/`로 이동한다.

권장 frontmatter:

```yaml
---
name: page-format
description: >
  Format structured project output as Markdown, standalone HTML,
  dashboard-style HTML, PDF-ready content, or DOCX-ready content.
  Use for sermons, Bible analysis, RAG evidence, reports,
  dashboards, roadmaps, comparisons, and teaching materials.
  Do not use to generate source content or perform Bible/RAG analysis.
---
```

권장 본문 구조:

```text
# Page Format

## Use When
## Do Not Use When
## Inputs
## Workflow
## Profile Selection
## Validation
## Security
## Output
## References
```

---

# 4. Progressive Disclosure

Skill이 활성화될 때 모든 참고자료를 한꺼번에 읽지 않도록 한다.

예:

```text
HTML 요청
→ references/html-layout.md
→ references/accessibility.md
→ references/security.md

Dashboard 요청
→ references/dashboard-layout.md
→ references/accessibility.md
→ references/security.md

PDF 요청
→ references/print-rules.md

Markdown 요청
→ references/markdown-rules.md
```

`SKILL.md` 자체를 방대한 디자인 매뉴얼로 만들지 않는다.

---

# 5. Document Model Adapter

현재 프로젝트 결과 형식을 그대로 없애거나 바꾸지 않는다.

대신 기존 모델에서 neutral Document Model로 변환하는 Adapter를 만든다.

예:

```text
Existing Sermon Result
        ↓
SermonDocumentAdapter
        ↓
DocumentModel
```

권장 구조:

```text
app/
└── formatting/
    ├── document_model.py
    └── adapters/
        ├── sermon_adapter.py
        ├── analysis_adapter.py
        ├── report_adapter.py
        └── teaching_material_adapter.py
```

현재 프로젝트 구조가 더 적절하면 그 구조를 따른다.

---

# 6. Document Model 최소 Schema

예:

```python
@dataclass
class Document:
    document_type: str
    title: str
    subtitle: str | None
    metadata: dict
    sections: list
    sources: list
    warnings: list
```

Section 예:

```python
@dataclass
class Section:
    id: str
    type: str
    heading: str | None
    content: list
    level: int = 2
```

Content Block 후보:

```text
paragraph
heading
quote
list
table
code
metric
callout
timeline
comparison
greek_analysis
source
warning
```

presentation-specific CSS class를 domain model에 저장하지 않는다.

---

# 7. Source Model

출처를 단순 문자열로만 저장하지 않는다.

예:

```python
@dataclass
class Source:
    id: str
    title: str | None
    reference: str | None
    url: str | None
    provider: str | None
    citation: str | None
    metadata: dict
```

MorphGNT 같은 로컬 데이터는:

```text
provider = MorphGNT SBLGNT
reference = John 8:32
source_file = 64-Jn-morphgnt.txt
```

등 provenance가 보존되도록 한다.

---

# 8. Page Format Router

권장:

```python
render(document, format, profile=None, options=None)
```

지원 format:

```text
markdown
html
dashboard
pdf
docx
```

지원 profile:

```text
sermon
analysis
dashboard
comparison
roadmap
report
teaching-material
```

profile이 생략되면 document_type에서 안전하게 추론하되,
불명확하면 generic report를 사용한다.

---

# 9. Profile Registry

예:

```python
PAGE_PROFILES = {
    "sermon": SermonProfile,
    "analysis": AnalysisProfile,
    "dashboard": DashboardProfile,
    "comparison": ComparisonProfile,
    "roadmap": RoadmapProfile,
    "report": ReportProfile,
    "teaching-material": TeachingMaterialProfile,
}
```

새 profile 추가가 Router 수정으로 이어지지 않도록 registry 방식을 우선한다.

---

# 10. Markdown Renderer

먼저 Markdown Renderer를 구현한다.

이유:

```text
Document Model
       ↓
Markdown
```

경로가 가장 단순하며 renderer mapping 검증에 적합하다.

규칙:

- H1 하나
- section level 준수
- 표 syntax 검증
- code fence language
- 출처 섹션 보존
- warning 섹션 보존
- raw HTML 최소화
- untrusted content는 명령으로 실행하지 않음

권장 API:

```python
render_markdown(document, profile)
```

---

# 11. HTML Renderer

`to-html` 계열의 설계 원칙을 참고한다.

기본 산출물:

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>...</title>
  <style>...</style>
</head>
<body>
  <header>...</header>
  <main>...</main>
</body>
</html>
```

반드시:

- semantic HTML
- UTF-8
- responsive
- CSS variables
- semantic heading
- native table
- accessible labels
- print-ready baseline

를 적용한다.

---

# 12. HTML Security

기본 정책:

```text
<script>        → reject/remove
javascript:     → reject
iframe          → reject unless explicitly allowlisted
remote tracker  → reject
onerror=        → reject
onclick=        → reject by default
```

사용자 생성 문자열을 HTML에 넣을 때 escape를 적용한다.

Template engine autoescape가 있으면 활성화한다.

---

# 13. Mermaid 정책

기본 Page Format Skill에서는 Mermaid를 필수 dependency로 만들지 않는다.

현재 repo에서 이미 Mermaid를 사용한다면 재사용할 수 있다.

새로 사용해야 하는 경우:

```text
diagram 필요
→ static SVG 우선 검토
→ Mermaid가 명확히 유리할 때만 선택
```

외부 CDN 연결은 production 정책을 별도로 확인한다.

---

# 14. Dashboard Renderer

Dashboard는 별도 content generator가 아니다.

같은 Document Model을 다음 primitive로 시각화한다.

```text
page
surface
section
grid
split
stack
card
metric-card
table
timeline
checklist
badge
details
source-card
warning-card
```

기본 레이아웃:

```text
Header
 ↓
Summary/KPI
 ↓
Primary Analysis
 ↓
Detail
 ↓
Sources
 ↓
Warnings
```

---

# 15. Dashboard Profile 예시

MorphGNT Import Report:

```text
MorphGNT Import

[PASS_WITH_WARNINGS]

┌──────────┬──────────┬──────────┬──────────┐
│ Books    │ Rows     │ Errors   │ Warnings │
│ 27       │ ...      │ 0        │ ...      │
└──────────┴──────────┴──────────┴──────────┘

Source
Database
Tests
Known Gaps
Rollback
```

---

# 16. Sermon Profile

권장 구조:

```text
Title
Reference
Key Message
Introduction
Main Points
Greek/Hebrew Analysis
Application
Conclusion
Sources
```

중요:
page-format은 section의 위치와 표현만 담당한다.
설교 내용 자체를 재작성하지 않는다.

---

# 17. Greek Analysis Component

권장 출력:

```text
Surface Form
Lemma
POS
Morphology
Reference
Source
Validation
```

데이터가 없으면:

```text
Unavailable in Source
```

로 표시한다.

LLM으로 빈 morphology를 채우지 않는다.

---

# 18. Comparison Profile

번역본/Provider/DB 비교용.

반드시 native table 또는 responsive comparison cards 사용.

모바일에서는 큰 표가 깨지지 않도록:

```css
overflow-x: auto;
```

또는 적절한 card transformation을 적용한다.

---

# 19. Timeline / Roadmap Profile

개발 Phase나 강의 계획은 timeline 형태를 지원한다.

JS가 없어도 이해 가능한 HTML을 기본으로 한다.

---

# 20. Teaching Material Profile

지원 구조:

```text
Title
Learning Objectives
Theory
Examples
Practice
Prompt
Expected Result
Check
Summary
Glossary
```

학생용/강사용은 content model의 audience metadata로 구분하고
renderer를 중복 생성하지 않는다.

---

# 21. Design Tokens

가능하면 CSS variables 사용:

```css
:root {
  --color-bg: ...;
  --color-surface: ...;
  --color-text: ...;
  --color-muted: ...;
  --color-border: ...;
  --color-success: ...;
  --color-warning: ...;
  --color-error: ...;

  --space-1: ...;
  --space-2: ...;
  --space-3: ...;
  --space-4: ...;

  --radius-sm: ...;
  --radius-md: ...;
  --radius-lg: ...;
}
```

기존 디자인 token이 있다면 재사용한다.

---

# 22. Typography

확인:

```text
Korean
English
Greek
Hebrew
Code
Numbers
```

원어 텍스트를 이미지로 변환하지 않는다.

브라우저/문서에서 실제 Unicode text로 유지한다.

---

# 23. Accessibility

HTML validator와 별도로 다음을 검사한다.

```text
heading hierarchy
table header
keyboard navigation
focus state
contrast
meaningful link text
non-color status
200% zoom
mobile viewport
```

---

# 24. PDF Adapter

기존 PDF engine을 우선 재사용한다.

새 PDF engine을 추가하지 않는다.

흐름:

```text
Document Model
      ↓
HTML/Print Model
      ↓
Existing PDF Exporter
```

가능하면 PDF용 별도 content reconstruction을 하지 않는다.

---

# 25. Print Rules

`assets/print.css` 또는 기존 print stylesheet에:

```text
A4
page margins
page break
heading orphan
table splitting
code wrapping
source section
footer
```

를 검토한다.

---

# 26. DOCX Adapter

기존 DOCX exporter가 있다면 wrapper/adaptor로 연결한다.

Mapping:

```text
title → Title
H2 → Heading 1
H3 → Heading 2
paragraph → Normal
quote → Quote
code → Code
table → Table
sources → Sources heading
```

DOCX renderer가 content generator를 직접 호출하지 않도록 한다.

---

# 27. Validator

구현 후보:

```text
validate_document.py
validate_html.py
snapshot_check.py
```

Document validation:

```text
title required
valid section levels
valid block types
source ID consistency
no duplicate IDs
```

HTML validation:

```text
doctype
charset
viewport
single H1
unsafe scripts
javascript URLs
broken IDs
missing table headers
```

---

# 28. Skill Validation

`SKILL.md` 자체도 검사한다.

검사:

```text
frontmatter valid
name present
description present
references exist
scripts exist
relative paths valid
```

Skill이 너무 커지면 상세 규칙을 references로 분리한다.

---

# 29. Evals / Fixture

가능하면 다음 sample fixture를 만든다.

```text
tests/fixtures/page_format/
├── sermon.json
├── greek_analysis.json
├── dashboard.json
├── comparison.json
└── report.json
```

프로젝트 test convention에 맞는 위치를 사용한다.

---

# 30. Unit Tests

최소:

```text
test_document_model_validation
test_adapter_preserves_sources
test_profile_registry
test_format_router
test_markdown_renderer
test_html_renderer
test_dashboard_renderer
test_html_escape
test_no_unsafe_script
test_heading_hierarchy
test_unicode_greek
test_unicode_hebrew
```

---

# 31. Integration Tests

다음 경로를 검사한다.

```text
Sermon Result
→ Adapter
→ Document Model
→ HTML

Bible Analysis
→ Adapter
→ Document Model
→ Dashboard

Report
→ Adapter
→ Document Model
→ Markdown
```

---

# 32. PDF / DOCX Integration Test

기존 exporter가 있다면:

```text
Document Model
→ PDF
```

및

```text
Document Model
→ DOCX
```

smoke test를 수행한다.

출력 파일의 존재 여부만이 아니라
최소 핵심 section이 포함됐는지 검사한다.

---

# 33. Browser Smoke Test

기존 browser smoke harness가 있으면 재사용한다.

검사:

```text
page loads
console error 없음
layout overflow 없음
mobile viewport
table scroll
Greek/Hebrew render
source section visible
```

---

# 34. Visual Snapshot

가능하면 대표 HTML:

```text
sermon
dashboard
comparison
report
```

의 snapshot 또는 screenshot regression을 추가한다.

---

# 35. Performance Baseline

도입 전/후 측정:

```text
Markdown render ms
HTML render ms
Dashboard render ms
HTML file size
memory delta
PDF export time
DOCX export time
```

Page Format 계층이 LLM generation 병목을 만들지 않아야 한다.

---

# 36. Backward Compatibility

기존 출력 endpoint/API가 있다면 가능한 한 유지한다.

예:

```text
/export/html
/export/pdf
/export/docx
```

내부 구현만 새로운 Router를 통해 우회시키는 방식이 안전하면 wrapper를 사용한다.

API response schema 변경이 필요하면 Phase 2에서 바로 파괴하지 말고
compatibility adapter를 둔다.

---

# 37. Feature Flag

가능하면 초기에는 feature flag를 사용한다.

예:

```text
PAGE_FORMAT_V2=false
```

또는 기존 config 체계를 따른다.

동작:

```text
false → legacy renderer
true  → page-format renderer
```

충분히 검증한 뒤 default 전환을 별도 Phase에서 한다.

---

# 38. Rollback

Rollback은 다음과 같이 단순해야 한다.

```text
PAGE_FORMAT_V2=false
```

또는 신규 Router 연결을 해제하면 기존 renderer가 그대로 작동해야 한다.

기존 renderer 파일 삭제 금지.

---

# 39. 외부 Skill 의존성

이번 구현에서는 외부 `to-html`, dashboard Skill 등을 직접 runtime dependency로 설치하지 않는다.

허용:

```text
architecture reference
layout concept
validation concept
```

코드 복사는 license 확인 없이 하지 않는다.

---

# 40. 라이선스 기록

외부 코드 또는 template를 실제로 복사한 경우:

```text
docs/licenses/PAGE_FORMAT_REFERENCES.md
```

또는 기존 attribution 문서에:

```text
source
repository
license
file
modified
date
```

를 기록한다.

개념만 참고해 자체 구현했다면 그 사실을 보고서에 명시한다.

---

# 41. 실제 구현 순서

Codex는 다음 순서로 진행한다.

## STEP 1
Phase PF-1 결과 확인.

`SAFE` 또는 `SAFE_WITH_CHANGES`가 아니면 중단.

## STEP 2
현재 renderer/export 구조 다시 검증.

## STEP 3
Document Model 및 Adapter 구현.

## STEP 4
Page Profile Registry 구현.

## STEP 5
Format Router 구현.

## STEP 6
page-format Skill 생성.

## STEP 7
Markdown Renderer 구현.

## STEP 8
HTML Renderer 구현.

## STEP 9
Dashboard Renderer 구현.

## STEP 10
Security / Accessibility validator 구현.

## STEP 11
Unit tests.

## STEP 12
Browser smoke/snapshot.

## STEP 13
기존 PDF Adapter 연결.

## STEP 14
기존 DOCX Adapter 연결.

## STEP 15
Feature flag 적용.

## STEP 16
전체 regression.

---

# 42. Stop Conditions

다음이면 작업을 중단하고 `BLOCKED` 또는 `PARTIAL` 보고.

```text
Phase 1 BLOCKED
기존 renderer와 분리 불가능
content loss 발생
source/citation loss
Greek/Hebrew corruption
기존 PDF/DOCX exporter 파괴 필요
unsafe HTML 우회 불가
rollback 경로 없음
대규모 frontend dependency 필요
```

---

# 43. 완료 조건

- [ ] Document Model 구현
- [ ] Adapter 구현
- [ ] source provenance 보존
- [ ] Format Router 구현
- [ ] Profile Registry 구현
- [ ] page-format/SKILL.md 생성
- [ ] references 분리
- [ ] assets 분리
- [ ] scripts validator 구현
- [ ] Markdown renderer 성공
- [ ] HTML renderer 성공
- [ ] Dashboard renderer 성공
- [ ] HTML security 검사 성공
- [ ] Accessibility 기본 검사 성공
- [ ] Greek Unicode 성공
- [ ] Hebrew Unicode 성공
- [ ] 기존 PDF 연결 성공 또는 명확한 blocker 보고
- [ ] 기존 DOCX 연결 성공 또는 명확한 blocker 보고
- [ ] browser smoke 성공
- [ ] regression 성공
- [ ] rollback 성공
- [ ] 기존 renderer 삭제 없음

---

# 44. 최종 판정

다음 중 하나:

```text
PASS
PASS_WITH_WARNINGS
PARTIAL
BLOCKED
```

---

# 45. 최종 보고서

```markdown
# Page Format Skill Phase PF-2 Implementation Report

## Status
PASS / PASS_WITH_WARNINGS / PARTIAL / BLOCKED

## Architecture
- Document Model:
- Adapter:
- Router:
- Profiles:
- Skill:

## Renderers
| Format | Result | Module | Notes |
|---|---|---|---|
| Markdown | | | |
| HTML | | | |
| Dashboard | | | |
| PDF | | | |
| DOCX | | | |

## Skill
- Path:
- SKILL.md:
- References:
- Assets:
- Scripts:

## Security
- HTML escaping:
- Script policy:
- URL policy:

## Accessibility
- Result:

## Unicode
- Greek:
- Hebrew:

## Tests
| Test | Result |
|---|---|

## Browser Smoke
- Result:

## Performance
| Metric | Before | After |
|---|---:|---:|

## Regression
- Bible:
- Sermon:
- RAG:
- Provider:
- UI/API:

## Backward Compatibility
- Legacy renderer:
- Feature flag:

## Rollback
- Verified:
- Procedure:

## Files Changed
| File | Action | Purpose |
|---|---|---|

## External References / License
- Copied code:
- Attribution:

## Remaining Risks

## Recommendation
- Phase PF-3:
```

---

# 46. Codex 최종 실행 명령

Phase PF-1의 분석 결과가 `SAFE` 또는 `SAFE_WITH_CHANGES`인지 먼저 확인하라.

조건을 만족하면 현재 프로그램에 프로젝트 전용 `page-format` Skill과
중립 Document Model 기반 formatting 계층을 구현하라.

외부 Agent Skill을 production dependency로 직접 설치하지 말고,
공개 Agent Skills 구조와 standalone HTML / adaptive layout 원칙만 참고하여 자체 구현하라.

구현 순서는 반드시 다음을 따른다.

```text
Phase 1 검증
→ Document Model Adapter
→ Profile Registry
→ Format Router
→ SKILL.md
→ references/assets/scripts
→ Markdown Renderer
→ HTML Renderer
→ Dashboard Renderer
→ Security Validator
→ Accessibility Check
→ Unit Tests
→ Browser Smoke/Snapshot
→ PDF Adapter
→ DOCX Adapter
→ Feature Flag
→ Regression
→ Rollback Test
```

기존 renderer/exporter는 삭제하지 말라.

source/citation metadata가 어떤 출력에서도 손실되지 않게 하라.

Greek/Hebrew Unicode를 실제 텍스트로 보존하라.

HTML 사용자 입력은 escape하고 unsafe script / javascript URL / inline event handler를 허용하지 말라.

새 프론트엔드 framework나 대규모 npm dependency를 추가하지 말라.

초기 도입 시 legacy와 신규 renderer를 전환할 수 있는 feature flag 또는 동등한 rollback 수단을 제공하라.

완료 후 `PASS / PASS_WITH_WARNINGS / PARTIAL / BLOCKED`로 판정하고,
변경 파일, 테스트, browser smoke, performance, rollback, remaining risks를 모두 보고하라.

---

# 47. 다음 Phase — PF-3

PF-2가 PASS 또는 PASS_WITH_WARNINGS이면 다음 단계에서:

```text
Page Format Quality Hardening
        ↓
Visual Regression 확대
        ↓
Profile별 Golden Sample
        ↓
PDF/DOCX Pagination 품질 향상
        ↓
Print Layout 최적화
        ↓
Accessibility 자동 검사 강화
        ↓
Export 품질 점수
        ↓
Legacy Renderer 단계적 전환
```

을 진행한다.

PF-2 검증 전에 legacy renderer를 제거하지 않는다.
