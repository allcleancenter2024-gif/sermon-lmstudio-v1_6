from unittest.mock import Mock

from app.constants import recommended_generation_model
from app.main import _select_generation_model, workflow_config


def test_duration_policy_prefers_long_context_models_when_ready():
    ready = ["qwen/qwen3-8b", "qwen/qwen3.5-9b", "qwen/qwen3.5-27b"]
    assert recommended_generation_model(15, ready) == "qwen/qwen3.5-9b"
    assert recommended_generation_model(20, ready) == "qwen/qwen3.5-9b"
    assert recommended_generation_model(25, ready) == "qwen/qwen3.5-27b"
    assert recommended_generation_model(30, ready) == "qwen/qwen3.5-27b"


def test_duration_policy_matches_lm_studio_instance_suffixes():
    ready = ["qwen/qwen3-8b:3", "qwen/qwen3.5-9b:2"]
    assert recommended_generation_model(15, ready) == "qwen/qwen3.5-9b:2"


def test_duration_policy_falls_back_to_current_ready_model():
    assert recommended_generation_model(30, ["qwen/qwen3-8b"]) == "qwen/qwen3-8b"


def test_backend_auto_selection_uses_duration_and_manual_selection_wins():
    client = Mock()
    client.model_catalog.return_value = {
        "source": "openai_compatible",
        "generation_models": ["qwen/qwen3-8b", "qwen/qwen3.5-9b", "qwen/qwen3.5-27b"],
    }
    selected, _ = _select_generation_model(client, "", 30)
    assert selected == "qwen/qwen3.5-27b"
    selected, _ = _select_generation_model(client, "qwen/qwen3-8b", 30)
    assert selected == "qwen/qwen3-8b"


def test_workflow_config_exposes_the_same_duration_policy():
    policy = workflow_config()["recommended_generation_models"]
    assert policy["15"][0] == "qwen/qwen3.5-9b"
    assert policy["30"][0] == "qwen/qwen3.5-27b"
