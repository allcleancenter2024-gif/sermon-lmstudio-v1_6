"""Fixture-safe adapters for one-section canary execution.

This adapter normalizes a single request into a SectionBuildResult.  It has no
knowledge of persistence, HTTP, model clients, or output formats.
"""

from __future__ import annotations

from typing import Any

from app.application.section_contracts import SectionRegenerationRequest, validate_section_result
from app.application.section_registry import SectionBuildResult, SectionBuilder


def build_one_section(request: SectionRegenerationRequest, builder: SectionBuilder) -> SectionBuildResult:
    request_errors = request.validate()
    if request_errors:
        return SectionBuildResult(request.section_id, "invalid", errors=tuple(request_errors))
    try:
        result = builder.build(request.context, request.evidence)
        validation_errors = tuple(str(error) for error in builder.validate(result))
        if validation_errors:
            return SectionBuildResult(request.section_id, "invalid", errors=validation_errors)
        output = SectionBuildResult(request.section_id, "ready", render_data=dict(builder.to_render_data(result)))
    except Exception as exc:  # one section must fail independently
        return SectionBuildResult(request.section_id, "failed", errors=(f"{type(exc).__name__}: {exc}",))
    contract_errors = validate_section_result(output)
    if contract_errors:
        return SectionBuildResult(request.section_id, "invalid", errors=tuple(contract_errors))
    return output


def build_fixture_sections(
    requests: tuple[SectionRegenerationRequest, ...],
    builders: dict[str, SectionBuilder],
) -> list[SectionBuildResult]:
    """Run fixture builders independently in request order."""
    return [
        build_one_section(request, builders[request.section_id])
        if request.section_id in builders
        else SectionBuildResult(request.section_id, "unregistered", errors=("builder is not registered",))
        for request in requests
    ]


__all__ = ["build_fixture_sections", "build_one_section"]
