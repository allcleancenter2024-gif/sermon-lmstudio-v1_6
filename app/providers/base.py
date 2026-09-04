"""Provider contracts shared by local and future model adapters."""

from typing import Any, Protocol


class ProviderAdapter(Protocol):
    """Minimum contract required by sermon generation and RAG callers."""

    def model_catalog(self) -> dict[str, Any]: ...

    def chat(self, model: str, system: str, user: str, temperature: float = 0.1) -> str: ...

    def embeddings(self, model: str, texts: list[str]) -> list[list[float]]: ...


def validate_provider_adapter(provider: object) -> None:
    """Fail closed when a future adapter does not implement all operations."""
    missing = [name for name in ("model_catalog", "chat", "embeddings") if not callable(getattr(provider, name, None))]
    if missing:
        raise TypeError("Provider Adapter 계약이 불완전합니다: " + ", ".join(missing))
