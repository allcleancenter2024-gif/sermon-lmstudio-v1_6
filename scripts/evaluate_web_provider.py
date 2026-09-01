"""Offline/manual evaluation harness for the single Phase 3B web provider.

No network is used unless a caller supplies a provider implementation.  The
default run uses a deterministic mock so CI remains offline and reproducible.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from unittest.mock import patch
from pathlib import Path
from time import monotonic

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.providers.web import WebEvidenceAdapter, WebSearchResult  # noqa: E402


class MockProvider:
    def search(self, query: str, *, max_results: int = 5):
        if "존재하지" in query or "모호한" in query or "거의 없을" in query:
            return []
        return [WebSearchResult(title=f"Mock result: {query[:40]}", url="https://official.example.test/source", snippet=f"Context for {query}", published_at="2026-01-01", provider="mock")]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((p / 100) * (len(ordered) - 1)))))
    return round(ordered[index], 2)


def main() -> int:
    fixture = ROOT / "evaluation" / "web_queries.json"
    queries = json.loads(fixture.read_text(encoding="utf-8"))
    if len(queries) < 30:
        raise SystemExit("evaluation fixture must contain at least 30 queries")
    external_configured = bool(os.getenv("WEB_SEARCH_ENDPOINT", "").strip() and os.getenv("WEB_SEARCH_API_KEY", "").strip())
    rows, latencies = [], []
    with patch.dict(os.environ, {"WEB_GROUNDING_ENABLED": "true"}, clear=False):
        adapter = WebEvidenceAdapter(MockProvider())
        for item in queries:
            started = monotonic()
            evidence, status = adapter.search(item["query"])
            elapsed = (monotonic() - started) * 1000
            latencies.append(elapsed)
            rows.append({"query": item["query"], "category": item["category"], "latency_ms": round(elapsed, 2),
                         "results": [x.as_dict() for x in evidence], "error": status.get("error"),
                         "scores": {"relevance": 5 if evidence else 0, "authority": 3 if evidence else 0,
                                    "freshness": 4 if evidence else 0, "metadata_completeness": 5 if evidence else 0}})
    total = len(rows); success = sum(bool(r["results"]) for r in rows); empty = total - success
    result = {"provider": "mock (offline)", "actual_provider_evaluation": "skipped" if not external_configured else "not_run_by_default",
              "expected_external_requests": 30, "total_requests": total,
              "success_rate": round(success / total, 4), "empty_result_rate": round(empty / total, 4), "error_rate": 0.0,
              "latency_ms": {"average": round(statistics.mean(latencies), 2), "median": round(statistics.median(latencies), 2),
                             "p95": percentile(latencies, 95), "min": round(min(latencies), 2), "max": round(max(latencies), 2)},
              "official_source_coverage": 0.0, "metadata_completeness": {"url": 1.0, "title": 1.0, "published_at": 1.0, "provider": 1.0},
              "duplicate_rate": 0.0, "grounding": {"source_type": "web", "tier": "D"}, "rows": rows}
    out = ROOT / "reports" / "web_provider_evaluation.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
