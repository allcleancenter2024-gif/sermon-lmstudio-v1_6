---
name: page-format
description: >
  Format structured project output as Markdown, standalone HTML,
  dashboard-style HTML, PDF-ready content, or DOCX-ready content.
  Use for sermons, Bible analysis, RAG evidence, reports, roadmaps,
  comparisons, and teaching materials. Do not generate source content
  or perform Bible/RAG analysis.
---

# Page Format

## Use When

Use after content exists and must be represented consistently in a document or page.

## Do Not Use When

Do not use to generate sermon content, search the Bible, run RAG, or infer missing Greek/Hebrew morphology.

## Inputs

Accept a validated `Document` model. Keep content, provenance, warnings, and presentation separate.

## Workflow

1. Build or adapt the document model.
2. Validate IDs, section levels, blocks, and sources.
3. Resolve a registered page profile.
4. Route to Markdown, HTML, Dashboard, PDF, or DOCX.
5. Preserve source metadata and warnings.
6. Run the relevant security, accessibility, and regression checks.

## Guardrails

- Keep legacy exporters and fallback paths available; V2 is the validated default and `PAGE_FORMAT_V2=false` remains the explicit rollback switch.
- Escape untrusted values; reject scripts, event handlers, `javascript:` URLs, trackers, and unapproved iframes.
- Do not add remote fonts, CDN assets, frontend frameworks, or external Skill runtime dependencies.
- Preserve Greek/Hebrew as Unicode text and show unavailable source data as unavailable.

## Progressive Disclosure

- HTML: read `references/html-layout.md`, `references/accessibility.md`, and `references/security.md`.
- Dashboard: read `references/dashboard-layout.md` and the accessibility/security references.
- PDF: read `references/print-rules.md`.
- Markdown: read `references/markdown-rules.md`.
- Quality: read `references/quality-gates.md` and `references/visual-regression.md`.
- PDF/DOCX: read the corresponding `references/pdf-quality.md` or `references/docx-quality.md`.

## Output

Use `app.formatting.format_router.render()` for text formats and `render_to_path()` for PDF/DOCX adapters.

## Quality Gate

Before final output: validate the document, render it, run format-specific checks, compare an approved golden sample when applicable, run accessibility/security checks, and report the quality score.
