import pytest

from app.providers.base import provider_capabilities, validate_provider_adapter
from app.providers.registry import create_provider, provider_specs


class IncompleteProvider:
    def chat(self, *args, **kwargs):
        return ""


def test_lmstudio_is_the_only_explicitly_enabled_provider():
    assert [(item.key, item.local_only, item.enabled) for item in provider_specs()] == [("lmstudio", True, True)]


def test_unregistered_provider_is_rejected():
    with pytest.raises(ValueError, match="등록되지 않았거나"):
        create_provider("openai")


def test_incomplete_provider_contract_fails_closed():
    with pytest.raises(TypeError, match="Provider Adapter 계약"):
        validate_provider_adapter(IncompleteProvider())


def test_lmstudio_factory_preserves_local_url():
    provider = create_provider("lmstudio", base_url="http://127.0.0.1:12345/v1")
    assert provider.base_url == "http://127.0.0.1:12345/v1"


def test_lmstudio_capabilities_are_explicit_and_local_only():
    provider = create_provider("lmstudio")
    assert provider_capabilities(provider) == {
        "local_only": True,
        "streaming": True,
        "cancellation": True,
        "reasoning_suppressed": True,
        "embeddings": True,
    }


def test_older_provider_without_optional_capabilities_remains_compatible():
    class LegacyProvider:
        def model_catalog(self): return {}
        def chat(self, *args, **kwargs): return ""
        def embeddings(self, model, texts): return []

    validate_provider_adapter(LegacyProvider())
    assert provider_capabilities(LegacyProvider()) == {}
