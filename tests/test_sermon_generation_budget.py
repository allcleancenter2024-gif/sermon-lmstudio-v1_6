from app.services.sermon_service import _resize_max_tokens, _sermon_max_tokens, _should_auto_resize


def test_generation_budget_scales_but_has_safe_bounds():
    assert _sermon_max_tokens(15) == 3000
    assert _sermon_max_tokens(30) == 4096
    assert _sermon_max_tokens(40) == 4096
    assert _sermon_max_tokens(15, "qwen/qwen3-4b") == 512


def test_resize_budget_is_smaller_than_full_generation_budget():
    assert _resize_max_tokens(15) == 600
    assert _resize_max_tokens(30) == 600


def test_qwen3_skips_slow_full_sermon_rewrite_pass():
    assert _should_auto_resize("qwen/qwen3-4b") is False
    assert _should_auto_resize("llama-3.1-8b") is True
