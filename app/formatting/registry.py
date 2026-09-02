from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .profiles import PAGE_PROFILES


@dataclass(frozen=True)
class TemplateSpec:
    id: str
    version: int
    profile: str
    formats: frozenset[str]
    themes: frozenset[str]
    status: str = "stable"


@dataclass(frozen=True)
class ThemeSpec:
    name: str
    tokens: dict[str, str]
    status: str = "stable"


@dataclass(frozen=True)
class ExportPreset:
    name: str
    format: str
    profile: str | None
    theme: str
    options: dict[str, Any]


TEMPLATES = {
    "sermon.standard": TemplateSpec("sermon.standard", 1, "sermon", frozenset({"markdown", "html", "pdf", "docx"}), frozenset({"default", "print", "high-contrast"})),
    "analysis.standard": TemplateSpec("analysis.standard", 1, "analysis", frozenset({"markdown", "html", "dashboard"}), frozenset({"default", "high-contrast"})),
    "dashboard.standard": TemplateSpec("dashboard.standard", 1, "dashboard", frozenset({"html", "dashboard", "markdown"}), frozenset({"default", "compact", "high-contrast"})),
    "report.standard": TemplateSpec("report.standard", 1, "report", frozenset({"markdown", "html", "pdf", "docx"}), frozenset({"default", "print", "high-contrast"})),
    "generic.standard": TemplateSpec("generic.standard", 1, "generic", frozenset({"markdown", "html"}), frozenset({"default", "high-contrast"})),
}

THEMES = {
    "default": ThemeSpec("default", {"color-bg": "#f4f7f5", "color-surface": "#ffffff", "color-text": "#17231f", "color-primary": "#245d50", "color-warning": "#fff4d8"}),
    "pastel": ThemeSpec("pastel", {"color-bg": "#f6f4fb", "color-surface": "#ffffff", "color-text": "#28233a", "color-primary": "#65558f", "color-warning": "#fff4d8"}),
    "high-contrast": ThemeSpec("high-contrast", {"color-bg": "#ffffff", "color-surface": "#ffffff", "color-text": "#000000", "color-primary": "#003b73", "color-warning": "#fff1a8"}),
    "print": ThemeSpec("print", {"color-bg": "#ffffff", "color-surface": "#ffffff", "color-text": "#111111", "color-primary": "#173b68", "color-warning": "#ffffff"}),
    "compact": ThemeSpec("compact", {"color-bg": "#f4f7f5", "color-surface": "#ffffff", "color-text": "#17231f", "color-primary": "#245d50", "color-warning": "#fff4d8"}),
}

PRESETS = {
    "web-standard": ExportPreset("web-standard", "html", None, "default", {"responsive": True, "print_css": True, "standalone": True}),
    "web-dashboard": ExportPreset("web-dashboard", "dashboard", "dashboard", "default", {"responsive": True, "compact_kpi": True}),
    "print-a4": ExportPreset("print-a4", "pdf", None, "print", {"paper": "A4", "margin": "standard"}),
    "docx-editable": ExportPreset("docx-editable", "docx", None, "default", {"styles": "semantic", "editable": True}),
    "markdown-source": ExportPreset("markdown-source", "markdown", None, "default", {"canonical": True}),
}


def select_output(*, document_type: str, format: str, profile: str | None = None, theme: str | None = None, preset: str | None = None) -> dict[str, Any]:
    selected_profile = profile or document_type
    if selected_profile not in PAGE_PROFILES:
        selected_profile = "generic"
    selected_theme = theme if theme in THEMES else "default"
    selected_preset = PRESETS.get(preset or "")
    selected_format = format.lower()
    warnings: list[str] = []
    if selected_preset:
        compatible = selected_format == selected_preset.format or {selected_format, selected_preset.format} <= {"html", "dashboard"}
        if not compatible:
            warnings.append(f"preset format {selected_preset.format} is incompatible with requested format {selected_format}; request kept")
            selected_preset = None
        else:
            selected_format = selected_preset.format
            selected_theme = selected_preset.theme
            if selected_preset.profile:
                selected_profile = selected_preset.profile
    else:
        if preset: warnings.append("unknown preset; format default used")
    template_id = f"{selected_profile}.standard"
    template = TEMPLATES.get(template_id) or TEMPLATES["generic.standard"]
    if selected_format not in template.formats or selected_theme not in template.themes:
        warnings.append(f"unsupported combination: {selected_profile} × {selected_format} × {selected_theme}")
        selected_profile, selected_format, selected_theme = "generic", "html", "default"
        template = TEMPLATES["generic.standard"]
    return {"profile": selected_profile, "format": selected_format, "theme": selected_theme, "preset": selected_preset.name if selected_preset else None, "template": template, "warnings": warnings}


def compatibility_matrix() -> dict[str, dict[str, tuple[str, ...]]]:
    """Expose the reviewed profile/format/theme contract for diagnostics and UI."""
    return {
        template.profile: {fmt: tuple(sorted(template.themes)) for fmt in sorted(template.formats)}
        for template in TEMPLATES.values()
    }
