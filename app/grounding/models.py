from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GroundingContext:
    main_passage: str | None = None
    selected_translation: str | None = None
    denomination: str | None = None
    allowed_source_types: set[str] | None = None
    strictness: str = "normal"
    db_path: object | None = None


@dataclass
class GroundingDecision:
    tier: str
    status: str
    reason: str
    confidence: float | None = None
    metadata: dict = field(default_factory=dict)
