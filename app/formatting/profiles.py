from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PageProfile:
    name: str
    heading: str
    description: str

    def validate(self, document: Any) -> list[str]:
        """Validate a document without coupling profile selection to renderers."""
        from .document_model import validate_document
        return validate_document(document)

    def map_sections(self, document: Any) -> list[Any]:
        """Return the canonical section order used by all output adapters."""
        return list(document.sections)

    def default_theme(self) -> str:
        return "print" if self.name in {"report", "sermon"} else "default"

    def allowed_export_presets(self) -> tuple[str, ...]:
        from .registry import PRESETS
        return tuple(name for name, preset in PRESETS.items() if preset.profile in {None, self.name})


PAGE_PROFILES = {
    name: PageProfile(name, heading, description)
    for name, heading, description in (
        ("sermon", "설교문", "설교 원고와 근거"),
        ("analysis", "분석", "성경·원어 분석"),
        ("dashboard", "대시보드", "상태와 지표"),
        ("comparison", "비교", "비교 결과"),
        ("roadmap", "로드맵", "단계별 진행"),
        ("report", "보고서", "검증 보고서"),
        ("teaching-material", "교재", "학습 자료"),
    )
}
PAGE_PROFILES["greek-analysis"] = PAGE_PROFILES["analysis"]


def resolve_profile(document_type: str, profile: str | None = None) -> PageProfile:
    name = profile or document_type
    return PAGE_PROFILES.get(name, PAGE_PROFILES["report"])
