import os
from unittest.mock import patch

from app.grounding.validator import validate_evidence
from app.providers.web import WebEvidenceAdapter, WebSearchResult, build_web_query, should_search_web


def test_web_disabled_does_not_call_provider():
    provider = type("P", (), {"search": lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError())})()
    with patch.dict(os.environ, {"WEB_GROUNDING_ENABLED": "false"}, clear=False):
        evidence, status = WebEvidenceAdapter(provider).search("최근 통계")
    assert evidence == []
    assert status["enabled"] is False


def test_web_results_normalize_as_tier_d_and_dedupe_safe_urls():
    class Provider:
        def search(self, query, *, max_results=5):
            return [WebSearchResult("A", "https://example.test/a?utm_source=x", "snippet"),
                    WebSearchResult("A duplicate", "https://example.test/a", "other"),
                    WebSearchResult("Bad", "javascript:alert(1)", "bad")]

    with patch.dict(os.environ, {"WEB_GROUNDING_ENABLED": "true"}, clear=False):
        evidence, status = WebEvidenceAdapter(Provider()).search("최근 통계")
    assert len(evidence) == 1
    assert evidence[0].source_type == "web"
    assert evidence[0].metadata["url"] == "https://example.test/a"
    assert validate_evidence(evidence[0]).tier == "D"
    assert status["results"] == 1


def test_provider_failure_falls_back():
    class Provider:
        def search(self, *args, **kwargs):
            raise TimeoutError()

    with patch.dict(os.environ, {"WEB_GROUNDING_ENABLED": "true"}, clear=False):
        evidence, status = WebEvidenceAdapter(Provider()).search("최근 통계")
    assert evidence == []
    assert status["fallback"] is True


def test_query_is_bounded_and_need_is_explicit():
    assert should_search_web("최근 한국 통계")
    assert not should_search_web("요한복음 3:16 설교")
    assert len(build_web_query("x" * 300, "y" * 300)) <= 240
