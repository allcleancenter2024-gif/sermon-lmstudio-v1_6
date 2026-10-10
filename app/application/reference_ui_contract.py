"""Read-only presentation contract for the related-reference dashboard.

This module converts the immutable reference catalog into UI data only.  It
does not render HTML, call the network, mutate the catalog, or apply a source
to Bible/project data.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.reference_catalog import ReferenceCatalog


@dataclass(frozen=True)
class ReferenceMenuItem:
    id: str = "related-references"
    label: str = "[관련자료참고]"
    target: str = "referenceSourcesPanel"
    note: str = "검증 상태와 출처·라이선스를 확인한 뒤 별도 승인 절차로 적용합니다."


def build_reference_dashboard(catalog: ReferenceCatalog) -> dict[str, object]:
    """Return safe, read-only data for a future related-reference panel."""
    errors = catalog.validate()
    return {
        "menu": ReferenceMenuItem().__dict__.copy(),
        "title": "[관련자료참고]",
        "notice": "자료는 읽기 전용으로 표시되며 검증되지 않은 출처는 적용할 수 없습니다.",
        "catalog_valid": not errors,
        "catalog_errors": list(errors),
        "sources": [source.as_dict() for source in catalog.sources],
        "applyable_source_ids": [source.id for source in catalog.applyable()],
        "apply_action": {
            "label": "[관련내용 적용]",
            "enabled": False,
            "reason": "실제 적용은 출처·라이선스 검증과 사용자 승인 후 별도 단계에서 활성화합니다.",
        },
    }


__all__ = ["ReferenceMenuItem", "build_reference_dashboard"]
