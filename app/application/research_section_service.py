"""Application service for the staged research Section canary.

The service composes a pure builder with the versioned Section repository.
It does not initialize a database, select a provider, or expose HTTP routes.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Protocol

from app.application.canary_adapters import build_one_section
from app.application.section_contracts import SectionRegenerationRequest
from app.application.section_registry import SectionBuilder


class SectionVersionRepository(Protocol):
    def require_ready(self) -> None: ...
    def create_version(self, **values: Any) -> dict[str, Any]: ...


class ResearchSectionService:
    """Generate one registered Section and persist an immutable result version."""

    def __init__(
        self,
        repository: SectionVersionRepository,
        builders: dict[str, SectionBuilder],
    ):
        self._repository = repository
        self._builders = dict(builders)

    def generate(self, project_id: int, request: SectionRegenerationRequest) -> dict[str, Any]:
        builder = self._builders.get(request.section_id)
        if builder is None:
            raise ValueError(f"builder is not registered: {request.section_id}")

        # Schema readiness must be checked before a Builder can invoke an LLM,
        # RAG, or any other expensive dependency.
        self._repository.require_ready()

        coverage = request.evidence.get("citation_coverage", 0.0)
        try:
            source_coverage = float(coverage)
        except (TypeError, ValueError) as exc:
            raise ValueError("citation_coverage must be numeric") from exc
        if not 0 <= source_coverage <= 1:
            raise ValueError("citation_coverage must be between 0 and 1")

        build_result = build_one_section(request, builder)
        persistence_status = {
            "ready": "ready",
            "invalid": "insufficient_evidence",
            "failed": "failed",
        }.get(build_result.status)
        if persistence_status is None:
            raise ValueError(f"unsupported build status: {build_result.status}")

        if build_result.status == "ready":
            content = dict(build_result.render_data or {})
            quality_status = "passed"
        else:
            content = {"errors": list(build_result.errors), "attempt": request.attempt}
            quality_status = "warning" if build_result.status == "invalid" else "failed"

        stored = self._repository.create_version(
            project_id=project_id,
            section_type=request.section_id,
            status=persistence_status,
            content=content,
            source_coverage=source_coverage,
            quality_status=quality_status,
            review_status="unreviewed",
            source_snapshot_id=request.source_snapshot_id,
        )
        return {"build": asdict(build_result), "section": stored}

    def retry(self, project_id: int, request: SectionRegenerationRequest) -> dict[str, Any]:
        return self.generate(project_id, request.retry())


__all__ = ["ResearchSectionService", "SectionVersionRepository"]
