"""Deterministic legacy/FTS5/hybrid RAG comparison baseline."""

from __future__ import annotations

import pytest

from app.core import build_rag_index, init_db
from app.rag.backend import compare_ranked_ids
from app.rag.fts import fts5_supported, fts_search, lexical_strategy
from app.rag.hybrid import compare_fusion_rankings, fusion_strategy, hybrid_search
from app.repositories.bible import add_passage, search_passages


class _DeterministicEmbeddingClient:
    def embeddings(self, model, texts):
        vectors = []
        for text in texts:
            value = str(text).lower()
            vectors.append([
                1.0 if "faith" in value else 0.0,
                1.0 if "courage" in value else 0.0,
            ])
        return vectors


def test_legacy_fts5_and_hybrid_rankings_are_compared_without_default_switch(tmp_path, monkeypatch):
    db = tmp_path / "rag-baseline.db"
    init_db(db)
    add_passage("TEST", "en", "TEST 1:1", "faith alone", "test-only", db)
    add_passage("TEST", "en", "TEST 1:2", "courage alone", "test-only", db)
    add_passage("TEST", "en", "TEST 1:3", "faith and courage", "test-only", db)

    monkeypatch.delenv("RAG_LEXICAL_STRATEGY", raising=False)
    monkeypatch.delenv("RAG_FUSION_STRATEGY", raising=False)
    assert lexical_strategy() == "legacy"
    assert fusion_strategy() == "legacy_weighted"
    if not fts5_supported(db):
        pytest.skip("SQLite FTS5 is unavailable in this test environment")

    client = _DeterministicEmbeddingClient()
    assert build_rag_index(client, "golden-embed", db) == 3

    legacy = search_passages("faith courage", db_path=db)
    fts5 = fts_search("faith courage", db_path=db)
    lexical_comparison = compare_ranked_ids(legacy, fts5, limit=3)

    hybrid_legacy = hybrid_search(
        "faith courage", client, "golden-embed", limit=3, db_path=db,
        strategy="legacy", fusion="legacy_weighted",
    )
    hybrid_fts5 = hybrid_search(
        "faith courage", client, "golden-embed", limit=3, db_path=db,
        strategy="fts5", fusion="legacy_weighted",
    )
    hybrid_comparison = compare_ranked_ids(hybrid_legacy, hybrid_fts5, limit=3)

    assert [item["reference"] for item in legacy] == ["TEST 1:1", "TEST 1:2", "TEST 1:3"]
    assert [item["reference"] for item in fts5] == ["TEST 1:3", "TEST 1:1", "TEST 1:2"]
    assert lexical_comparison == {
        "baseline_ids": [1, 2, 3],
        "candidate_ids": [3, 1, 2],
        "overlap_count": 3,
        "baseline_count": 3,
        "candidate_count": 3,
        "overlap_rate": 1.0,
        "order_changed": True,
    }
    assert [item["reference"] for item in hybrid_legacy] == ["TEST 1:3", "TEST 1:1", "TEST 1:2"]
    assert [item["reference"] for item in hybrid_fts5] == ["TEST 1:3", "TEST 1:1", "TEST 1:2"]
    assert hybrid_comparison["overlap_rate"] == 1.0
    assert hybrid_comparison["order_changed"] is False


def test_rrf_canary_expanded_queries_preserve_legacy_top_k_overlap(tmp_path, monkeypatch):
    db = tmp_path / "rrf-canary.db"
    init_db(db)
    rows = [
        ("TEST", "en", "TEST 1:1", "faith alone"),
        ("TEST", "en", "TEST 1:2", "courage alone"),
        ("TEST", "en", "TEST 1:3", "faith and courage"),
        ("TEST", "en", "TEST 2:1", "faith and grace"),
        ("TEST", "en", "TEST 2:2", "courage and hope"),
        ("TEST", "en", "TEST 2:3", "faith courage grace"),
        ("TEST", "en", "TEST 2:4", "hope and peace"),
        ("TEST", "en", "TEST 2:5", "grace and mercy"),
    ]
    for translation, language, reference, text in rows:
        add_passage(translation, language, reference, text, "test-only", db)

    monkeypatch.delenv("RAG_LEXICAL_STRATEGY", raising=False)
    monkeypatch.delenv("RAG_FUSION_STRATEGY", raising=False)
    assert lexical_strategy() == "legacy"
    assert fusion_strategy() == "legacy_weighted"
    if not fts5_supported(db):
        pytest.skip("SQLite FTS5 is unavailable in this test environment")

    client = _DeterministicEmbeddingClient()
    assert build_rag_index(client, "rrf-canary-embed", db) == len(rows)
    queries = ["faith courage", "faith grace", "courage hope", "grace", "courage"]
    comparisons = []
    for query in queries:
        baseline = hybrid_search(
            query, client, "rrf-canary-embed", limit=5, db_path=db,
            strategy="legacy", fusion="legacy_weighted",
        )
        candidate = hybrid_search(
            query, client, "rrf-canary-embed", limit=5, db_path=db,
            strategy="legacy", fusion="rrf",
        )
        comparison = compare_fusion_rankings(baseline, candidate, limit=5, minimum_overlap=0.70)
        comparisons.append(comparison)

    assert comparisons
    assert min(item["overlap_rate"] for item in comparisons) >= 0.70
    assert all(item["approved_for_canary"] for item in comparisons)
    assert all(item["baseline_strategy"] == "legacy_weighted" for item in comparisons)
    assert all(item["candidate_strategy"] == "rrf" for item in comparisons)
    assert fusion_strategy() == "legacy_weighted"
