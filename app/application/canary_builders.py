"""Adapters that reuse existing services for the staged Section canary.

Only the structure adapter is enabled in Gate 2A.  Dependencies are injected
so importing this module cannot initialize SQLite or contact a provider.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


PassageStudyLoader = Callable[[str, list[dict[str, Any]] | None], dict[str, Any]]


class StructureBuilder:
    """Adapt the existing passage study into the `structure` section contract."""

    def __init__(self, load_passage_study: PassageStudyLoader):
        self._load_passage_study = load_passage_study

    def build(self, context: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        reference = str(context.get("reference") or "").strip()
        if not reference:
            raise ValueError("reference is required")
        related = context.get("related")
        if related is not None and not isinstance(related, list):
            raise ValueError("related must be a list")
        study = self._load_passage_study(reference, related)
        return {
            "section_id": "structure",
            "reference": reference,
            "translations": list(study.get("translations") or []),
            "context": list(study.get("context") or []),
            "related": list(study.get("related") or []),
            "warnings": list(study.get("warnings") or []),
            "counts": dict(study.get("counts") or {}),
            "source_ids": list(evidence.get("source_ids") or []),
        }

    def validate(self, result: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if result.get("section_id") != "structure":
            errors.append("section_id must be structure")
        if not str(result.get("reference") or "").strip():
            errors.append("reference is required")
        if not result.get("translations"):
            errors.append("registered main-passage text is required")
        return errors

    def to_render_data(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "section_id": result["section_id"],
            "title": "본문의 위치와 구조",
            "reference": result["reference"],
            "translations": list(result["translations"]),
            "context": list(result["context"]),
            "related": list(result["related"]),
            "warnings": list(result["warnings"]),
            "counts": dict(result["counts"]),
            "source_ids": list(result["source_ids"]),
        }


__all__ = ["PassageStudyLoader", "StructureBuilder"]
