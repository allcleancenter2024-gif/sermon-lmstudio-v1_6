"""Typed contracts shared by prompt composition boundaries."""

from __future__ import annotations

from typing import Any, Protocol


Row = dict[str, Any]


class SermonTimePlan(Protocol):
    def __call__(self, minutes: int, chars_per_minute: int = 330) -> dict[str, Any]: ...


class PassageSorter(Protocol):
    def __call__(self, passages: list[Row]) -> list[Row]: ...


class ReferenceRoundRobin(Protocol):
    def __call__(self, items: list[Row], limit: int) -> list[Row]: ...


class CompactOutlineStudy(Protocol):
    def __call__(self, study: dict[str, Any], aggressive: bool = False) -> dict[str, Any]: ...


class InterpretationFlowPrompt(Protocol):
    def __call__(
        self,
        passages: list[Row],
        word_notes: list[Row] | None = None,
        doctrine_notes: list[Row] | None = None,
    ) -> str: ...


class TranslationPolicyPrompt(Protocol):
    def __call__(self, passages: list[Row], word_notes: list[Row] | None = None) -> str: ...


class SocialContextPolicyPrompt(Protocol):
    def __call__(self, topic: str = "", details: str = "") -> str: ...


class GroundingBuilder(Protocol):
    def __call__(self, passages: list[Row], max_chars: int | None = None) -> str: ...
