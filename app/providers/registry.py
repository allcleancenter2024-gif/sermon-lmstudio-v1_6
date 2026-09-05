"""Explicit provider registry; unregistered providers are never activated."""

from dataclasses import dataclass

from app.providers.base import validate_provider_adapter
from app.providers.lmstudio import LMStudioClient


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    local_only: bool
    enabled: bool
    capabilities: tuple[str, ...] = ()


PROVIDER_SPECS = (
    ProviderSpec("lmstudio", "LM Studio", True, True,
                 ("streaming", "cancellation", "reasoning_suppressed", "embeddings")),
)


def provider_specs() -> tuple[ProviderSpec, ...]:
    return PROVIDER_SPECS


def create_provider(key: str = "lmstudio", **kwargs):
    """Create only explicitly registered adapters."""
    normalized = str(key or "").strip().lower()
    spec = next((item for item in PROVIDER_SPECS if item.key == normalized), None)
    if not spec or not spec.enabled:
        raise ValueError(f"등록되지 않았거나 비활성화된 Provider입니다: {key}")
    provider = LMStudioClient(**kwargs)
    validate_provider_adapter(provider)
    return provider
