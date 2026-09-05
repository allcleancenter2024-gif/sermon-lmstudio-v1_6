"""Provider contracts shared by local and future model adapters."""

from typing import Any, Protocol


class ProviderAdapter(Protocol):
    """Minimum contract required by sermon generation and RAG callers."""

    def model_catalog(self) -> dict[str, Any]: ...

    def chat(self, model: str, system: str, user: str, temperature: float = 0.1) -> str: ...

    def embeddings(self, model: str, texts: list[str]) -> list[list[float]]: ...

    def capabilities(self) -> dict[str, bool]: ...


def validate_provider_adapter(provider: object) -> None:
    """Fail closed when a future adapter does not implement all operations."""
    missing = [name for name in ("model_catalog", "chat", "embeddings") if not callable(getattr(provider, name, None))]
    if missing:
        raise TypeError("Provider Adapter 계약이 불완전합니다: " + ", ".join(missing))


def provider_capabilities(provider: object) -> dict[str, bool]:
    """Read optional capabilities without making older adapters invalid."""
    method = getattr(provider, "capabilities", None)
    if not callable(method):
        return {}
    result = method()
    if not isinstance(result, dict) or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in result.items()):
        raise TypeError("Provider capabilities는 문자열 키와 bool 값의 dict여야 합니다.")
    return dict(result)
