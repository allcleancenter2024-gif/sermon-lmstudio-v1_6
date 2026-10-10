from app.application import settings_facade
from app import config


def test_settings_facade_exposes_existing_runtime_contract():
    assert settings_facade.get_lmstudio_url is not None
    assert settings_facade.set_lmstudio_url is not None
    assert settings_facade.LMStudioClient is not None
    assert settings_facade.start_local_server is not None
    assert settings_facade.get_github_repository_url is not None


def test_settings_facade_owns_lmstudio_url_configuration_boundary():
    assert settings_facade.get_lmstudio_url is config.get_lmstudio_url
    assert settings_facade.set_lmstudio_url is config.set_lmstudio_url
