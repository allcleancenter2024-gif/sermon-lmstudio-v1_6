from __future__ import annotations

import html

from ..document_model import ContentBlock, Document


def _esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def render_html(document: Document, profile: str | None = None, options: dict | None = None) -> str:
    sections = []
    for section in document.sections:
        blocks = []
        for block in section.content:
            value = _esc(block.value)
            if block.type == "quote":
                blocks.append(f"<blockquote>{value}</blockquote>")
            elif block.type == "code":
                blocks.append(f"<pre><code>{value}</code></pre>")
            elif block.type == "warning":
                blocks.append(f'<aside class="warning" role="note">{value}</aside>')
            else:
                blocks.append(f"<p>{value}</p>")
        heading = f"<h{max(2, min(6, section.level))}>{_esc(section.heading or section.id)}</h{max(2, min(6, section.level))}>"
        sections.append(f"<section id=\"{_esc(section.id)}\">{heading}{''.join(blocks)}</section>")
    sources = "".join(f"<li data-source-id=\"{_esc(source.id)}\">[{_esc(source.id)}] {_esc(source.reference or source.title or source.id)}{f' · {_esc(source.provider)}' if source.provider else ''}</li>" for source in document.sources)
    warning_html = "".join(f'<li>{_esc(warning)}</li>' for warning in document.warnings)
    output = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{_esc(document.title)}</title><style>
:root{{--bg:#f4f7f5;--surface:#fff;--text:#17231f;--muted:#65756e;--line:#dbe4df;--accent:#245d50;--warn:#fff4d8}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.8 'Malgun Gothic','Noto Sans KR',sans-serif}}main{{max-width:960px;margin:0 auto;padding:30px 20px}}header,section,aside{{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:22px;margin:16px 0}}h1{{margin:0;color:var(--accent);font-size:clamp(26px,5vw,42px)}}h2,h3{{color:var(--accent)}}p{{white-space:pre-wrap}}blockquote{{margin:12px 0;padding:10px 14px;border-left:4px solid var(--accent);background:#eef7f2}}pre{{overflow:auto;background:#17231f;color:#fff;padding:14px;border-radius:8px;white-space:pre-wrap}}.warning{{background:var(--warn)}}@media print{{body{{background:#fff}}main{{max-width:none;padding:0}}header,section,aside{{border:0;padding:0;box-shadow:none;break-inside:auto}}}}@media(max-width:600px){{main{{padding:16px}}}}
</style></head><body><main><header><h1>{_esc(document.title)}</h1>{f'<p>{_esc(document.subtitle)}</p>' if document.subtitle else ''}</header>{''.join(sections)}{f'<section><h2>출처</h2><ul>{sources}</ul></section>' if sources else ''}{f'<section><h2>주의사항</h2><ul>{warning_html}</ul></section>' if warning_html else ''}</main></body></html>'''
    theme = str((options or {}).get("theme", "default"))
    from ..registry import THEMES
    tokens = THEMES.get(theme, THEMES["default"]).tokens
    css = ":root{" + ";".join(f"--{key}:{_esc(value)}" for key, value in tokens.items()) + "}"
    return output.replace("</style>", css + "</style>", 1)
