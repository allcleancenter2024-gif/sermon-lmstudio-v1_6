from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvidenceCandidate:
    source_id: str | None = None
    source_type: str = "unknown"
    source_name: str | None = None
    reference: str | None = None
    text: str = ""
    page: int | None = None
    chunk_id: str | None = None
    retrieval_type: str | None = None
    semantic_rank: int | None = None
    lexical_rank: int | None = None
    rrf_score: float | None = None
    metadata: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        """Return a backward-compatible mapping plus normalized metadata."""
        result = dict(self.metadata)
        result.update({
            "id": self.source_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "reference": self.reference,
            "text": self.text,
            "page": self.page,
            "chunk_id": self.chunk_id,
            "retrieval_type": self.retrieval_type,
            "semantic_rank": self.semantic_rank,
            "lexical_rank": self.lexical_rank,
            "rrf_score": self.rrf_score,
        })
        return {key: value for key, value in result.items() if value is not None}
