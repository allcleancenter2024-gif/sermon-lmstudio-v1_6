# PAGE_FORMAT_SKILL_INTEGRATION_PHASE4.md
# Codex 작업지시서 — Page Format Skill 통합 Phase PF-4
# Production Rollout Hardening · Template/Profile Registry · Theme · Export Preset · Telemetry · 점진적 전환

## 0. 실행 전제

이 작업은 **PF-3 결과가 `PASS` 또는 `PASS_WITH_WARNINGS`인 경우에만 실행**한다.

PF-3가 `PARTIAL` 또는 `BLOCKED`이면 PF-4를 시작하지 않는다.

이번 단계는 새 renderer를 만드는 단계가 아니라,
**검증된 Page Format V2를 실제 운영 환경에 안전하게 확장·전환하는 단계**다.

최종 목표:

```text
PF-3 Quality Gate
      ↓
Template/Profile Registry
      ↓
Theme Registry
      ↓
Export Presets
      ↓
User/Project Selection
      ↓
Quality Telemetry
      ↓
Legacy vs V2 Comparison
      ↓
Canary / Gradual Rollout
      ↓
Default V2 Decision
      ↓
Legacy Retirement Readiness
```

---

# 1. 핵심 원칙

1. PF-3 quality gate를 우회하지 않는다.
2. 기존 Legacy renderer를 즉시 삭제하지 않는다.
3. V2 default 전환은 단계적으로 수행한다.
4. 사용자 콘텐츠를 telemetry로 전송하지 않는다.
5. telemetry는 기본적으로 기술적 메타데이터만 수집한다.
6. theme/profile 선택이 content semantics를 바꾸지 않아야 한다.
7. PDF/DOCX/HTML/Markdown 모두 동일한 Document Model을 유지한다.
8. Source/Citation integrity는 모든 preset에서 필수다.
9. Greek/Hebrew Unicode 품질을 모든 preset에서 유지한다.
10. fallback 경로를 제거하기 전에 실제 운영 검증 기간을 둔다.
11. 신규 외부 Skill을 runtime dependency로 추가하지 않는다.
12. 새 frontend framework를 rollout 편의를 이유로 도입하지 않는다.

---

# 2. Agent Skill 구조 유지

Agent Skills 표준의 progressive disclosure 원칙을 유지한다.

권장 구조:

```text
page-format/
├── SKILL.md
├── evals/
├── scripts/
├── references/
└── assets/
```

PF-4에서 다음 reference를 추가할 수 있다.

```text
references/
├── profile-registry.md
├── theme-registry.md
├── export-presets.md
├── rollout-policy.md
├── telemetry-policy.md
└── legacy-retirement.md
```

SKILL.md는 라우팅과 핵심 workflow만 유지하고
운영 정책 전문은 references에 둔다.

---

# 3. Skill Self-Containment

Page Format Skill이 자신이 필요로 하는 reference/assets/scripts를
skill 디렉터리 내부에서 찾을 수 있도록 한다.

금지:

```text
Skill A → Skill B 내부 파일 직접 import
Skill → 임의 프로젝트 외부 template 참조
Skill → 사용자 홈 디렉터리의 비공식 파일 참조
```

공통 라이브러리가 필요하면
애플리케이션 코드 계층에서 명시적 dependency로 관리한다.

---

# 4. Profile Registry 정식화

PF-2/PF-3에서 사용한 profile을 정식 registry로 관리한다.

권장 profile:

```text
sermon
analysis
greek-analysis
dashboard
comparison
roadmap
report
teaching-material
generic
```

예:

```python
PAGE_PROFILES = {
    "sermon": SermonProfile,
    "analysis": AnalysisProfile,
    "greek-analysis": GreekAnalysisProfile,
    "dashboard": DashboardProfile,
    "comparison": ComparisonProfile,
    "roadmap": RoadmapProfile,
    "report": ReportProfile,
    "teaching-material": TeachingMaterialProfile,
    "generic": GenericProfile,
}
```

---

# 5. Profile Contract

모든 profile은 동일한 contract를 따른다.

예:

```python
class PageProfile:
    name: str

    def validate(document):
        ...

    def map_sections(document):
        ...

    def default_theme():
        ...

    def allowed_export_presets():
        ...
```

profile은 content를 생성하거나 재해석하지 않는다.

---

# 6. Profile Versioning

profile 변경이 기존 결과를 깨뜨릴 수 있으므로 version을 둔다.

예:

```text
sermon@1
dashboard@1
report@1
```

큰 visual/structural 변경 시:

```text
sermon@2
```

를 검토한다.

사소한 CSS 개선마다 version을 올릴 필요는 없다.

---

# 7. Template Registry

HTML template을 파일 경로 하드코딩으로 직접 선택하지 않는다.

Registry 예:

```python
TEMPLATES = {
    "report.standard": "...",
    "dashboard.standard": "...",
    "sermon.standard": "...",
}
```

Template metadata:

```text
id
version
profile
supported_formats
theme compatibility
locale
status
```

---

# 8. Template Status

다음 상태를 지원한다.

```text
experimental
preview
stable
deprecated
```

사용자 기본 출력에는 `stable`만 사용한다.

---

# 9. Theme Registry

Theme은 content 구조와 분리한다.

권장 theme:

```text
default
pastel
high-contrast
print
compact
```

현재 프로그램의 기존 디자인 시스템이 있으면 기존 theme 이름을 우선한다.

---

# 10. Theme Token Contract

Theme은 token 값을 제공한다.

예:

```text
color-bg
color-surface
color-text
color-muted
color-border
color-primary
color-success
color-warning
color-error

font-body
font-heading
font-greek
font-hebrew
font-code

space-1
space-2
space-3
space-4

radius-sm
radius-md
radius-lg
```

Theme이 DOM 구조를 직접 재정의하지 않도록 한다.

---

# 11. High Contrast Theme

접근성 용도로 별도 theme을 제공할 수 있다.

단:

```text
Theme = accessibility 해결책 전체
```

로 간주하지 않는다.

heading, keyboard, focus, semantic table 등은 theme과 무관하게
기본 renderer가 준수해야 한다.

---

# 12. Export Preset Registry

사용자가 format 외에 목적을 선택할 수 있도록 preset을 둔다.

예:

```text
web-standard
web-dashboard
print-a4
pdf-report
docx-editable
markdown-source
```

---

# 13. Export Preset Contract

예:

```python
class ExportPreset:
    name: str
    format: str
    profile: str | None
    theme: str | None
    options: dict
```

Preset이 renderer 내부에 조건문을 무한히 늘리지 않게 한다.

---

# 14. 권장 Preset

## web-standard

```text
format = html
responsive = true
print_css = true
standalone = true
```

## web-dashboard

```text
format = dashboard
responsive = true
compact_kpi = true
```

## print-a4

```text
format = pdf
paper = A4
margin = standard
```

## docx-editable

```text
format = docx
styles = semantic
editable = true
```

## markdown-source

```text
format = markdown
canonical = true
```

---

# 15. Locale / Language

향후 다국어를 고려해 profile과 theme에서 locale을 분리한다.

예:

```text
ko-KR
en-US
```

Greek/Hebrew는 locale이 아니라 content language/script로 취급한다.

---

# 16. 사용자 선택 UI

현재 프로그램에 export UI가 있다면
그 UI를 크게 재작성하지 않는다.

가능하면 다음 정도만 추가한다.

```text
Format
Profile
Theme
Preset
```

단, 일반 사용자는 너무 많은 옵션을 볼 필요가 없다.

기본 UI:

```text
출력 형식
스타일
```

고급 옵션에서 세부 profile/theme을 보여주는 방식을 검토한다.

---

# 17. Smart Default

대부분의 사용자는 profile을 수동 선택하지 않아도 되게 한다.

예:

```text
sermon document → sermon profile
analysis report → analysis
program status → dashboard
comparison → comparison
```

추론 결과가 불확실하면 `generic` 사용.

---

# 18. User Override

사용자가 명시적으로 profile/theme을 선택하면
자동 추론보다 우선한다.

단 incompatible 조합은 validator가 막는다.

예:

```text
profile=sermon
preset=web-dashboard
```

가 비정상인 경우 warning 또는 fallback.

---

# 19. Compatibility Matrix

다음 표를 코드 또는 config로 유지한다.

```text
Profile × Format × Theme × Preset
```

예:

```text
sermon × html × default × web-standard = supported
sermon × pdf × print × print-a4 = supported
dashboard × docx × compact = unsupported
```

---

# 20. Validation Before Render

Router는 render 전 다음을 확인한다.

```text
document valid
profile exists
template stable
theme exists
preset compatible
source metadata intact
```

실패 시 unsafe fallback을 하지 않는다.

---

# 21. Fallback Policy

권장:

```text
unknown profile → generic
unknown theme → default
unsupported preset → format default preset
```

하지만 source/citation 또는 document validation failure에는
fallback하지 말고 error를 반환한다.

---

# 22. Quality Telemetry

Telemetry는 운영 품질 판단을 위한 기술 메타데이터만 수집한다.

권장 event:

```text
render_started
render_completed
render_failed
quality_gate_failed
fallback_used
legacy_used
v2_used
export_completed
export_failed
```

---

# 23. Telemetry Privacy

기본적으로 수집 금지:

```text
설교 본문
사용자가 입력한 개인 텍스트
RAG 원문
성경 분석 전체 내용
API key
파일 내용
사용자 식별정보
```

허용 가능한 기술 메타데이터 예:

```text
format
profile
theme
preset
duration_ms
output_size
status
error_code
quality_score
renderer_version
```

현재 프로그램 privacy policy가 더 엄격하면 그것을 우선한다.

---

# 24. Error Code 표준화

문자열 stack trace만 telemetry에 보내지 않는다.

예:

```text
PF_DOC_INVALID
PF_PROFILE_UNKNOWN
PF_TEMPLATE_ERROR
PF_HTML_SECURITY
PF_PDF_EXPORT
PF_DOCX_EXPORT
PF_SOURCE_LOSS
PF_UNICODE_ERROR
PF_VISUAL_REGRESSION
```

stack trace는 기존 local logging 정책에 따른다.

---

# 25. Quality Score Telemetry

PF-3의 quality score를 운영 지표로 활용한다.

예:

```text
average_quality_score
quality_fail_rate
source_integrity_fail_rate
export_fail_rate
fallback_rate
```

사용자 콘텐츠는 저장하지 않는다.

---

# 26. Performance Budget

renderer별 성능 budget을 둔다.

PF-3 측정치를 baseline으로 사용한다.

예:

```text
HTML render
Dashboard render
PDF export
DOCX export
```

절대 시간 + PF-3 대비 delta를 같이 본다.

---

# 27. Performance Warning

예:

```text
baseline 대비 25% 이상 악화
```

시 warning.

하지만 매우 짧은 작업은 percentage noise를 고려한다.

---

# 28. Legacy vs V2 Comparison

같은 Document Model을:

```text
Legacy
V2
```

두 renderer로 출력할 수 있는 comparison mode를 개발/테스트 환경에 제공한다.

운영 사용자에게 두 결과를 항상 동시에 만들 필요는 없다.

---

# 29. Comparison Metrics

최소:

```text
title preserved
section count
source count
reference
table count
warnings
file size
render time
```

visual은 PF-3 Golden Sample을 사용한다.

---

# 30. Shadow Mode

가능하면 초기 rollout에서 V2를 사용자에게 직접 제공하지 않고
일부 테스트에서 shadow render를 수행할 수 있다.

예:

```text
Legacy → 실제 사용자 출력
V2 → 내부 검증만
```

단 shadow mode가 CPU/메모리를 과도하게 사용하면 사용하지 않는다.

---

# 31. Canary Rollout

Feature flag가 percentage rollout을 지원한다면 다음 단계 권장:

```text
0%
→ internal
→ 10%
→ 25%
→ 50%
→ 100%
```

현재 config 시스템이 percentage rollout을 지원하지 않으면
단순 environment/project-level rollout을 사용한다.

새 feature flag 플랫폼을 도입할 필요는 없다.

---

# 32. Rollout Gate

각 단계에서 다음을 확인한다.

```text
critical errors = 0
source integrity failure = 0
security failure = 0
export fail rate acceptable
quality score acceptable
performance budget acceptable
rollback verified
```

---

# 33. Stop / Rollback Conditions

다음 중 하나면 rollout을 중단한다.

```text
source/citation loss
HTML security regression
PDF/DOCX corruption
Greek/Hebrew corruption
critical accessibility regression
failure rate 급증
render latency 심각한 악화
memory spike
rollback 실패
```

즉시 legacy로 되돌릴 수 있어야 한다.

---

# 34. Default V2 전환 조건

다음 조건을 모두 만족한 후에만:

```text
PAGE_FORMAT_V2=true
```

를 default로 검토한다.

- PF-3 PASS 계열
- PF-4 rollout gates 통과
- 대표 profile 모두 stable
- source integrity 안정
- PDF/DOCX 안정
- accessibility critical 0
- security critical 0
- rollback 검증
- 관찰 기간 동안 major incident 없음

---

# 35. 관찰 기간

정확한 날짜를 임의로 강제하지 않는다.

현재 프로젝트 배포 주기와 사용자 수를 기준으로 정한다.

보고서에:

```text
observation period
sample size
render count
failure count
```

를 기록한다.

---

# 36. Legacy Deprecation 단계

Legacy renderer는 다음 순서로 처리한다.

```text
active
→ fallback-only
→ deprecated
→ removal-candidate
→ removed
```

PF-4에서는 최대 `removal-candidate`까지만 판정한다.

실제 삭제는 별도 Phase에서 한다.

---

# 37. Legacy Removal Readiness

다음 조건이 필요하다.

```text
V2 default 안정
fallback 사용률 충분히 낮음
legacy-only bug 없음
legacy-only profile 없음
rollback 대체 전략 존재
```

---

# 38. Legacy 코드 직접 삭제 금지

PF-4에서는:

```text
rm legacy_renderer
```

와 같은 파괴적 작업을 하지 않는다.

삭제 후보 목록만 보고한다.

---

# 39. Template Deprecation

Template도 version/status를 관리한다.

예:

```text
report.standard@1 stable
report.standard@2 preview
```

전환 시 기존 template을 바로 삭제하지 않는다.

---

# 40. Migration Rules

Template/Profile/Preset config schema가 변경될 경우
migration을 제공한다.

예:

```text
old preset name
→ new preset name
```

unknown old value는 default로 조용히 덮지 말고 warning 기록.

---

# 41. Config Version

가능하면:

```text
page_format_config_version
```

을 둔다.

예:

```text
1
```

향후 schema 변경을 추적할 수 있게 한다.

---

# 42. Export File Naming

파일명 생성 규칙을 중앙화한다.

예:

```text
<title>_<profile>_<YYYYMMDD>.<ext>
```

그러나 filesystem 안전 문자를 고려한다.

금지:

```text
renderer마다 서로 다른 파일명 규칙
```

---

# 43. Duplicate-safe Export

같은 파일명이 존재하는 경우:

```text
overwrite 여부
dedupe
version suffix
```

를 기존 프로그램 정책에 맞춘다.

사용자 파일을 조용히 덮어쓰지 않는다.

---

# 44. Export Metadata

가능하면 출력 결과와 함께 metadata를 생성한다.

예:

```json
{
  "renderer": "page-format-v2",
  "profile": "sermon",
  "theme": "default",
  "preset": "pdf-report",
  "quality_score": 95
}
```

파일 내부에 넣을지 sidecar로 둘지는 기존 구조를 따른다.

---

# 45. Evals 유지

Agent Skill의 `evals/` 또는 프로젝트 테스트 fixture를 유지한다.

다음 trigger/use case를 검사한다.

```text
설교 HTML
원어 분석 dashboard
RAG report
강의자료 PDF
비교표 HTML
Markdown source
```

---

# 46. Skill Trigger Evals

page-format Skill이:

```text
필요할 때 활성화
불필요할 때 비활성화
```

되는지 검사한다.

False positive 예:

```text
“요한복음 8장 뜻을 설명해줘”
```

→ content analysis task이므로 page-format Skill 단독 trigger가 되어서는 안 된다.

True positive:

```text
“이 설교 결과를 dashboard HTML로 만들어줘”
```

---

# 47. SKILL.md Validation

계속 확인:

```text
name valid
description valid
body size 적절
references reachable
scripts reachable
assets reachable
```

SKILL.md가 운영 정책 때문에 비대해지지 않게 한다.

---

# 48. Accessibility 운영 Gate

WCAG 2.2 방향의 PF-3 검사 기준을 유지한다.

특히 rollout 중 다음 악화를 감시한다.

```text
focus
heading
table semantics
contrast
reflow
status text
```

Theme 추가가 접근성을 깨뜨리지 않는지 검사한다.

---

# 49. Theme Accessibility Test

모든 stable theme에 최소:

```text
contrast
focus visible
status non-color
zoom/reflow
```

test를 실행한다.

---

# 50. Security 운영 Gate

각 stable template/theme/preset 조합에서:

```text
script injection
javascript URL
inline handler
unsafe iframe
remote tracker
```

검사를 유지한다.

---

# 51. Remote Resource Policy

기본:

```text
local/inline assets 우선
```

외부 리소스가 꼭 필요한 경우:

```text
domain
purpose
privacy impact
offline impact
```

을 명시한다.

---

# 52. Offline Compatibility

현재 프로그램이 로컬/오프라인 사용을 지원한다면
stable preset은 외부 CDN 없이 작동해야 한다.

최소:

```text
HTML open offline
CSS available
Greek/Hebrew font fallback
no required network calls
```

검사.

---

# 53. Observability Dashboard

기존 dashboard 시스템이 있으면
운영자용 작은 Page Format 상태 영역을 추가할 수 있다.

표시 후보:

```text
V2 adoption
render success
export success
fallback count
avg quality score
avg render time
```

새 dashboard 시스템을 만들지는 않는다.

---

# 54. Alert Threshold

자동 알림 인프라가 이미 있으면 다음에 활용 가능:

```text
failure rate spike
source integrity failure
security critical
PDF export failure spike
```

새 alert 시스템 구축은 이번 Phase 범위 밖이다.

---

# 55. Logging

로그에 사용자 본문 전체를 남기지 않는다.

좋은 예:

```text
render_id
profile
preset
duration
status
error_code
```

나쁜 예:

```text
full sermon text
full RAG evidence
API secrets
```

---

# 56. Render ID

한 번의 render/export를 추적할 수 있도록
비식별 random render ID를 사용할 수 있다.

예:

```text
render_id = UUID
```

사용자 identity와 직접 연결할 필요는 없다.

---

# 57. Test Matrix

최소 matrix:

```text
Profile:
sermon
analysis
dashboard
comparison
report
teaching-material

Format:
markdown
html
pdf
docx

Theme:
default
high-contrast
print
```

모든 조합을 무조건 테스트하지 말고
지원되는 compatibility matrix만 실행한다.

---

# 58. Smoke Matrix

대표 조합:

```text
sermon × html × default
sermon × pdf × print
analysis × dashboard × default
comparison × html × default
report × docx × default
teaching-material × pdf × print
```

---

# 59. Regression Matrix

검사:

```text
Document Model
source integrity
Unicode
security
accessibility
visual
performance
export
rollback
```

---

# 60. Codex 실행 순서

## STEP 1
PF-3 최종 보고서를 확인한다.

## STEP 2
현재 feature flag/config 구조를 분석한다.

## STEP 3
Profile Registry 정식화.

## STEP 4
Template Registry 구현.

## STEP 5
Theme Registry 구현.

## STEP 6
Export Preset Registry 구현.

## STEP 7
Compatibility Matrix 구현.

## STEP 8
Smart Default + User Override 구현.

## STEP 9
Validation / fallback policy 구현.

## STEP 10
기술 telemetry 설계/연결.

## STEP 11
Legacy vs V2 comparison test.

## STEP 12
Canary/gradual rollout 준비.

## STEP 13
Performance/quality rollout gate.

## STEP 14
Rollback test.

## STEP 15
Legacy retirement readiness 평가.

## STEP 16
전체 regression.

---

# 61. Stop Conditions

다음이면 `PARTIAL` 또는 `BLOCKED`.

```text
PF-3 PASS 계열 아님
profile/template registry가 기존 구조를 파괴해야 함
source/citation 손실
privacy-safe telemetry 구성 불가
feature flag rollback 불가
stable theme 접근성 critical
export preset이 PDF/DOCX를 깨뜨림
legacy와 V2 동시 유지 불가
```

---

# 62. 완료 조건

- [ ] PF-3 PASS 계열 확인
- [ ] Profile Registry
- [ ] Profile version/status
- [ ] Template Registry
- [ ] Theme Registry
- [ ] Export Preset Registry
- [ ] Compatibility Matrix
- [ ] Smart Default
- [ ] User Override
- [ ] validation/fallback
- [ ] privacy-safe telemetry
- [ ] error codes
- [ ] performance budget
- [ ] legacy vs V2 comparison
- [ ] gradual rollout strategy
- [ ] rollout gates
- [ ] rollback verified
- [ ] stable theme accessibility
- [ ] stable template security
- [ ] offline compatibility
- [ ] skill evals
- [ ] full regression
- [ ] Legacy renderer not deleted

---

# 63. 최종 판정

```text
PASS
PASS_WITH_WARNINGS
PARTIAL
BLOCKED
```

추가로 다음을 별도 판정한다.

```text
V2_DEFAULT_READY = YES / NO
LEGACY_REMOVAL_READY = YES / NO
```

---

# 64. 최종 보고서 형식

```markdown
# Page Format Skill Phase PF-4 Production Rollout Report

## Status
PASS / PASS_WITH_WARNINGS / PARTIAL / BLOCKED

## Readiness
- V2_DEFAULT_READY:
- LEGACY_REMOVAL_READY:

## Registries
- Profiles:
- Templates:
- Themes:
- Export Presets:

## Compatibility Matrix
| Profile | Format | Theme | Preset | Supported |
|---|---|---|---|---|

## Smart Defaults
- Result:

## User Overrides
- Result:

## Telemetry
- Events:
- Privacy:
- Stored content:
- Error codes:

## Quality
- Average score:
- Critical failures:

## Performance
| Renderer | PF-3 Baseline | PF-4 | Delta |
|---|---:|---:|---:|

## Accessibility
- Stable themes:
- Critical:
- Major:

## Security
- Stable templates:
- Critical:

## Offline
- Result:

## Legacy vs V2
| Metric | Legacy | V2 |
|---|---:|---:|

## Rollout
- Strategy:
- Current stage:
- Gates:

## Rollback
- Verified:
- Procedure:

## Legacy Retirement
- Current state:
- Missing conditions:
- Candidate files:

## Tests / Evals
| Test | Result |
|---|---|

## Files Changed
| File | Action | Purpose |
|---|---|---|

## Remaining Risks

## Recommendation
- Phase PF-5:
```

---

# 65. Codex 최종 실행 명령

Phase PF-3의 결과가 `PASS` 또는 `PASS_WITH_WARNINGS`인지 먼저 확인하라.

조건을 만족하면 Page Format V2를 production rollout 가능한 구조로 강화하라.

새 content generator나 새 frontend framework를 만들지 말라.

다음을 순서대로 구현하라.

```text
PF-3 검증
→ Profile Registry
→ Template Registry
→ Theme Registry
→ Export Preset Registry
→ Compatibility Matrix
→ Smart Defaults
→ User Overrides
→ Validation/Fallback
→ Privacy-safe Telemetry
→ Performance Budget
→ Legacy vs V2 Comparison
→ Canary/Gradual Rollout
→ Rollout Gates
→ Rollback Verification
→ Legacy Retirement Readiness
→ Full Regression
```

Agent Skill은 self-contained하고 progressive disclosure 구조를 유지하라.

SKILL.md를 운영 정책 전체가 들어간 거대한 파일로 만들지 말고
상세 정책은 references에 분리하라.

Telemetry에 사용자의 설교 본문, RAG 원문, 파일 내용, API key,
개인 식별정보를 저장하지 말라.

Source/Citation integrity failure, security critical, Unicode corruption,
PDF/DOCX corruption은 rollout 중단 조건으로 취급하라.

V2 default 전환 전 rollback을 반드시 검증하라.

PF-4에서는 Legacy renderer를 삭제하지 말라.

마지막에:

```text
PASS / PASS_WITH_WARNINGS / PARTIAL / BLOCKED
V2_DEFAULT_READY = YES / NO
LEGACY_REMOVAL_READY = YES / NO
```

를 보고하고,
profile/template/theme/preset, telemetry, quality, performance,
accessibility, security, rollout, rollback, legacy retirement 조건을 모두 보고하라.

---

# 66. 다음 단계 — PF-5

PF-4가 PASS 또는 PASS_WITH_WARNINGS이고:

```text
V2_DEFAULT_READY = YES
```

일 때 다음 Phase에서:

```text
Default V2 Activation
      ↓
Production Observation
      ↓
Fallback Rate 분석
      ↓
Legacy-only Dependency 제거
      ↓
Legacy Removal Dry Run
      ↓
Rollback Archive
      ↓
Legacy Renderer Decommission
```

을 검토한다.

PF-4에서 `LEGACY_REMOVAL_READY = YES`가 나왔더라도
실제 Legacy 코드 삭제는 PF-5에서 별도로 실행한다.
