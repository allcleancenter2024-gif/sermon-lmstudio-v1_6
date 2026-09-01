"""Evidence normalization helpers."""

from .models import EvidenceCandidate
from .normalize import normalize_evidence, dedupe_evidence

__all__ = ["EvidenceCandidate", "normalize_evidence", "dedupe_evidence"]
