"""Pure Section Builder registry for the five-section canary.

The registry owns ordering and failure isolation only.  It deliberately does
not know about SQLite, HTTP, providers, prompts, or output renderers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


CANARY_SECTION_IDS = (
    "structure",
    "original_language_keywords",
    "verse_commentary",
    "sermon_form_guide",
    "research_book",
)


class SectionBuilder(Protocol):
    def build(self, context: dict[str, Any], evidence: dict[str, Any]) -> Any: ...

    def validate(self, result: Any) -> list[str]: ...

    def to_render_data(self, result: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SectionSpec:
    id: str
    label: str
    order: int
    enabled: bool = True


@dataclass(frozen=True)
class SectionBuildResult:
    section_id: str
    status: str
    render_data: dict[str, Any] | None = None
    errors: tuple[str, ...] = ()


CANARY_SECTIONS = tuple(
    SectionSpec(section_id, label, order)
    for section_id, label, order in (
        ("structure", "본문의 위치와 구조", 20),
        ("original_language_keywords", "원어 핵심 어휘", 30),
        ("verse_commentary", "절별 주석", 40),
        ("sermon_form_guide", "설교 형식 적용 가이드", 50),
        ("research_book", "설교 준비 자료집", 60),
    )
)


class SectionRegistry:
    """Run registered builders independently while preserving deterministic order."""

    def __init__(self, specs: tuple[SectionSpec, ...] = CANARY_SECTIONS, builders: dict[str, SectionBuilder] | None = None):
        self._specs = tuple(sorted(specs, key=lambda item: (item.order, item.id)))
        self._builders = dict(builders or {})
        self._validate_specs()

    def _validate_specs(self) -> None:
        ids = [spec.id for spec in self._specs]
        if len(ids) != len(set(ids)):
            raise ValueError("section id must be unique")
        if any(not spec.id.strip() or not spec.label.strip() for spec in self._specs):
            raise ValueError("section id and label are required")

    def specs(self) -> tuple[SectionSpec, ...]:
        return self._specs

    def build(self, context: dict[str, Any], evidence: dict[str, Any]) -> list[SectionBuildResult]:
        results: list[SectionBuildResult] = []
        for spec in self._specs:
            if not spec.enabled:
                results.append(SectionBuildResult(spec.id, "disabled"))
                continue
            builder = self._builders.get(spec.id)
            if builder is None:
                results.append(SectionBuildResult(spec.id, "unregistered", errors=("builder is not registered",)))
                continue
            try:
                result = builder.build(context, evidence)
                validation_errors = tuple(str(error) for error in builder.validate(result))
                if validation_errors:
                    results.append(SectionBuildResult(spec.id, "invalid", errors=validation_errors))
                    continue
                results.append(SectionBuildResult(spec.id, "ready", render_data=dict(builder.to_render_data(result))))
            except Exception as exc:  # section failure must not abort other sections
                results.append(SectionBuildResult(spec.id, "failed", errors=(f"{type(exc).__name__}: {exc}",)))
        return results


__all__ = ["CANARY_SECTION_IDS", "CANARY_SECTIONS", "SectionBuildResult", "SectionBuilder", "SectionRegistry", "SectionSpec"]
