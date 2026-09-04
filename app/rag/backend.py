"""Explicit RAG backend capability and regression comparison contracts.

SQLite remains the production default.  PostgreSQL/pgvector is represented as
an opt-in capability only; this phase does not connect, migrate, or reindex it.
"""

from dataclasses import dataclass
import os


SUPPORTED_BACKENDS = ("sqlite", "postgres_pgvector")


@dataclass(frozen=True)
class RagBackendSettings:
    name: str = "sqlite"
    enabled: bool = True

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "RagBackendSettings":
        env = os.environ if environ is None else environ
        name = env.get("RAG_BACKEND", "sqlite").strip().lower() or "sqlite"
        if name not in SUPPORTED_BACKENDS:
            raise ValueError(f"지원하지 않는 RAG backend입니다: {name}")
        enabled = env.get("RAG_BACKEND_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        if name == "postgres_pgvector" and enabled:
            raise RuntimeError("PostgreSQL·pgvector는 capability 검증 후에만 활성화할 수 있습니다.")
        return cls(name=name, enabled=enabled)


def compare_ranked_ids(baseline: list[dict], candidate: list[dict], limit: int = 10) -> dict:
    """Compare result overlap without changing either search strategy."""
    base_ids = [item.get("id") for item in baseline[:limit]]
    candidate_ids = [item.get("id") for item in candidate[:limit]]
    base_set, candidate_set = set(base_ids), set(candidate_ids)
    overlap = base_set & candidate_set
    return {
        "baseline_ids": base_ids,
        "candidate_ids": candidate_ids,
        "overlap_count": len(overlap),
        "baseline_count": len(base_ids),
        "candidate_count": len(candidate_ids),
        "overlap_rate": round(len(overlap) / len(base_set), 4) if base_set else 1.0,
        "order_changed": base_ids != candidate_ids,
    }
