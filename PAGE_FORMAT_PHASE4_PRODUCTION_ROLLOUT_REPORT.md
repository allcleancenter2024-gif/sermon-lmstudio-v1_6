# Page Format Skill Integration Phase 4 Production Rollout Report

## Status

`PASS_WITH_WARNINGS`

- `V2_DEFAULT_READY`: `NO` — the legacy renderer remains the safe default.
- `LEGACY_REMOVAL_READY`: `NO` — removal requires a later production observation window.
- Dependency changes: none required. The existing project `.venv` already contained the required test/runtime packages.

## Scope completed

Phase 4 rollout hardening is implemented while preserving the existing output path and keeping `PAGE_FORMAT_V2=false` as the default.

- Profile registry and contract: sermon, analysis, dashboard, comparison, roadmap, report, teaching-material, and generic fallback.
- Template registry: versioned stable templates with declared formats and themes.
- Theme registry: default, pastel, high-contrast, print, and compact tokens. HTML output now applies selected theme tokens safely.
- Export preset registry: web-standard, web-dashboard, print-a4, docx-editable, and markdown-source.
- Compatibility matrix and smart defaults: unsupported profile/theme/format combinations fall back to a safe generic HTML selection with a warning.
- User override handling: export payloads accept profile/theme/preset; incompatible presets cannot silently change an endpoint's output format.
- Rollout control: `PAGE_FORMAT_ROLLOUT=legacy|internal|canary|0-100`; deterministic hash bucketing supports gradual rollout and immediate rollback.
- Legacy compatibility: all four existing export endpoints continue to use legacy exporters unless V2 is explicitly enabled or selected by rollout.
- Privacy-safe telemetry: local technical JSONL events contain render ID, format, profile, theme, preset, duration, size, status, quality score, and approved error code only; sermon content and source text are not recorded.
- Error-code catalog: invalid document, template, HTML security, PDF/DOCX export, source loss, Unicode, and visual regression codes are defined.
- Quality/performance gates: existing quality score, source integrity, Unicode integrity, HTML security/accessibility checks, PDF/DOCX smoke checks, and golden profile metadata remain in the test suite.
- Offline operation: no external runtime assets or network dependency was introduced.
- Windows test permissions: pytest no longer forces a stale project-local temporary directory; test scratch data uses the current user's writable profile and pytest's isolated temporary directories.

## Files changed for Phase 4

- `app/formatting/profiles.py`
- `app/formatting/registry.py`
- `app/formatting/rollout.py`
- `app/formatting/format_router.py`
- `app/formatting/renderers/html.py`
- `app/formatting/renderers/dashboard.py`
- `app/formatting/telemetry.py`
- `app/routers/exports.py`
- `static/app.js`
- `templates/index.html`
- `tests/conftest.py`
- `pytest.ini`
- `tests/test_page_format.py`
- `tests/test_page_format_quality.py`
- `tests/test_page_format_rollout.py`
- `tests/page_format/golden/**`
- `.agents/skills/page-format/scripts/export_smoke.py`

## Compatibility and rollout gates

The rollout gate is intentionally conservative:

1. Default and rollback state: `PAGE_FORMAT_ROLLOUT=legacy` and `PAGE_FORMAT_V2=false`.
2. Internal validation: `PAGE_FORMAT_ROLLOUT=internal` selects V2 for all requests in an internal environment.
3. Canary: `PAGE_FORMAT_ROLLOUT=1` through `99` deterministically selects a percentage of render IDs.
4. Full evaluation: `PAGE_FORMAT_ROLLOUT=100` or `all` selects V2.
5. Any quality failure, export failure, source loss, or visual regression blocks promotion and returns to `legacy`.

The legacy renderer is not retired in this phase because no production traffic telemetry or connected browser visual-regression harness is available in this workspace. Manual browser approval is still required before enabling V2 globally.

## Verification

- Full regression: `284 passed, 7 subtests passed`
- `git diff --check`: passed; only normal Git LF/CRLF conversion warnings were reported.
- PDF/DOCX adapter smoke: passed in the Phase 3 quality gate (`VALID PDF`, `VALID DOCX`).
- Golden profiles checked: seven approved profile fixtures.
- Security check: HTML escaping and source integrity tests passed.
- No dependencies were installed or changed.

## Risks and follow-up

- Browser screenshot comparison is not automated in this environment; connect the app to the browser verification harness and approve each golden profile before turning on global V2.
- Project-level persistence of format preferences remains a future migration candidate; current overrides are request-scoped and therefore avoid a database schema change.
- Telemetry is local JSONL by design. A future dashboard may aggregate it, but must continue excluding document content and source text.

## Rollback

Set `PAGE_FORMAT_ROLLOUT=legacy` and leave `PAGE_FORMAT_V2=false`, then restart the launcher. Existing legacy exporters remain available and unchanged.

## Recommendation

Keep the current default on legacy, perform a short internal/canary observation window, compare quality/error/source-integrity metrics, and only then consider `PAGE_FORMAT_ROLLOUT=100`. Do not delete legacy output code until that observation is complete.
