from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from time import monotonic
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from app.evidence import dedupe_evidence, normalize_evidence
from app.evidence.models import EvidenceCandidate


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def web_grounding_enabled() -> bool:
    return _flag("WEB_GROUNDING_ENABLED")


def should_search_web(text: str) -> bool:
    """Return true only for explicit external/current-fact requests."""
    value = str(text or "").lower()
    return any(token in value for token in (
        "latest", "current", "recent", "통계", "뉴스", "최근", "현재", "사회 현상",
        "경제 상황", "역사적 배경", "외부 연구", "조사에 따르면", "연구에 따르면",
    ))


def build_web_query(topic: str, details: str = "", *, max_chars: int = 240) -> str:
    """Build a bounded query without forwarding an entire private sermon draft."""
    topic = " ".join(str(topic or "").split())[:160]
    detail = " ".join(str(details or "").split())[:80]
    return " ".join(x for x in (topic, detail) if x).strip()[:max_chars]


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str = ""
    published_at: str | None = None
    domain: str | None = None
    provider: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WebSearchProvider(Protocol):
    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]: ...


def _safe_url(value: Any) -> str | None:
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    # Remove common tracking parameters while preserving the actual URL.
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"gclid", "fbclid"}]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True), fragment=""))


class WebEvidenceAdapter:
    """Convert provider results to runtime EvidenceCandidate values (always Tier D)."""

    def __init__(self, provider: WebSearchProvider | None = None, *, max_results: int = 5):
        self.provider = provider or NullWebSearchProvider()
        self.max_results = max(1, min(int(max_results), 5))

    def search(self, query: str) -> tuple[list[EvidenceCandidate], dict[str, Any]]:
        if not web_grounding_enabled() or not str(query or "").strip():
            return [], {"enabled": web_grounding_enabled(), "provider_available": False, "fallback": False, "results": 0}
        started = monotonic()
        try:
            raw = self.provider.search(str(query).strip(), max_results=self.max_results)[: self.max_results]
            candidates: list[EvidenceCandidate] = []
            seen: set[str] = set()
            for item in raw:
                result = item if isinstance(item, WebSearchResult) else WebSearchResult(**dict(item))
                safe = _safe_url(result.url)
                if not safe or safe in seen:
                    continue
                seen.add(safe)
                metadata = dict(result.metadata)
                metadata.update({"title": result.title, "url": safe, "domain": result.domain or urlparse(safe).netloc,
                                 "snippet": result.snippet, "published_at": result.published_at,
                                 "retrieved_at": metadata.get("retrieved_at"), "provider": result.provider})
                candidates.append(normalize_evidence({"id": safe, "source_type": "web",
                    "source_name": result.title, "reference": safe, "text": result.snippet,
                    **metadata}, source_type="web"))
            return dedupe_evidence(candidates), {"enabled": True, "provider_available": True, "fallback": False,
                "results": len(candidates), "elapsed_ms": round((monotonic() - started) * 1000, 2)}
        except Exception as exc:  # provider failures must not break generation
            return [], {"enabled": True, "provider_available": False, "fallback": True, "results": 0,
                        "error": type(exc).__name__, "elapsed_ms": round((monotonic() - started) * 1000, 2)}


class NullWebSearchProvider:
    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        return []


class HttpJsonWebSearchProvider:
    """Single generic JSON provider adapter; endpoint/API key are environment-only."""

    def __init__(self, endpoint: str | None = None, *, api_key: str | None = None, timeout: float = 10.0):
        self.endpoint = endpoint or os.getenv("WEB_SEARCH_ENDPOINT", "").strip()
        self.api_key = api_key or os.getenv("WEB_SEARCH_API_KEY", "").strip()
        self.timeout = max(5.0, min(float(timeout), 15.0))

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        if not self.endpoint:
            return []
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(self.endpoint, data=json.dumps({"query": query, "max_results": max_results}).encode(), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"web provider unavailable: {type(exc).__name__}") from exc
        items = payload.get("results", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return []
        return [WebSearchResult(title=str(x.get("title", "")), url=str(x.get("url", "")), snippet=str(x.get("snippet", x.get("text", ""))),
                                 published_at=x.get("published_at"), domain=x.get("domain"), provider="http-json")
                for x in items[:max_results] if isinstance(x, dict)]
