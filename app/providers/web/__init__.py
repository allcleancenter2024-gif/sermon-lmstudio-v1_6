"""Optional web search provider abstractions.

The package intentionally performs no network activity unless a caller opts in
and supplies a configured provider.
"""

from .base import (
    HttpJsonWebSearchProvider,
    NullWebSearchProvider,
    WebEvidenceAdapter,
    WebSearchProvider,
    WebSearchResult,
    build_web_query,
    should_search_web,
    web_grounding_enabled,
)

__all__ = [
    "HttpJsonWebSearchProvider", "NullWebSearchProvider", "WebEvidenceAdapter",
    "WebSearchProvider", "WebSearchResult", "build_web_query",
    "should_search_web", "web_grounding_enabled",
]
