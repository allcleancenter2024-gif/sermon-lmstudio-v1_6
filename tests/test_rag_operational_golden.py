"""Anonymized operational-shaped RAG golden set for read-only canary comparison."""

from __future__ import annotations

from app.core import build_rag_index, init_db
from app.rag.hybrid import compare_fusion_rankings, hybrid_search
from app.rag.fts import lexical_strategy
from app.rag.hybrid import fusion_strategy
from app.rag.quality import evaluate_fusion_quality
from app.evidence.normalize import normalize_evidence
from app.repositories.bible import search_passages
from app.rag.semantic import semantic_search
from app.rag.hybrid import rrf_fusion
from app.repositories.bible import add_passage


class _OperationalGoldenEmbeddingClient:
    _terms = ("faith", "love", "hope", "justice", "peace", "forgiveness")

    def embeddings(self, model, texts):
        return [
            [1.0 if term in str(text).lower() else 0.0 for term in self._terms]
            for text in texts
        ]


def test_anonymized_operational_golden_queries_preserve_metadata_and_overlap(tmp_path, monkeypatch):
    db = tmp_path / "operational-golden.db"
    init_db(db)
    rows = [
        ("GOLDEN 1:1", "faith and hope"),
        ("GOLDEN 1:2", "love and forgiveness"),
        ("GOLDEN 1:3", "justice and peace"),
        ("GOLDEN 1:4", "faith love and hope"),
        ("GOLDEN 2:1", "forgiveness and peace"),
        ("GOLDEN 2:2", "justice love and mercy"),
        ("GOLDEN 2:3", "hope peace and comfort"),
        ("GOLDEN 2:4", "faith justice and courage"),
        ("GOLDEN 3:1", "love peace and reconciliation"),
        ("GOLDEN 3:2", "forgiveness faith and renewal"),
    ]
    for reference, text in rows:
        add_passage("GOLDEN", "en", reference, text, f"golden-license-{reference}", db)

    monkeypatch.delenv("RAG_LEXICAL_STRATEGY", raising=False)
    monkeypatch.delenv("RAG_FUSION_STRATEGY", raising=False)
    assert lexical_strategy() == "legacy"
    assert fusion_strategy() == "legacy_weighted"

    client = _OperationalGoldenEmbeddingClient()
    assert build_rag_index(client, "operational-golden-embed", db) == len(rows)
    queries = [
        "faith hope",
        "love forgiveness",
        "justice peace",
        "hope comfort",
        "faith renewal",
        "love peace",
        "faith peace",
        "justice love",
        "hope forgiveness",
        "peace forgiveness",
    ]
    relevance_labels = {
        "faith hope": {"GOLDEN 1:1", "GOLDEN 1:4", "GOLDEN 2:3", "GOLDEN 2:4", "GOLDEN 3:2"},
        "love forgiveness": {"GOLDEN 1:2", "GOLDEN 2:1", "GOLDEN 2:2", "GOLDEN 3:1", "GOLDEN 3:2"},
        "justice peace": {"GOLDEN 1:3", "GOLDEN 2:1", "GOLDEN 2:2", "GOLDEN 2:3", "GOLDEN 2:4", "GOLDEN 3:1"},
        "hope comfort": {"GOLDEN 1:1", "GOLDEN 1:4", "GOLDEN 2:3"},
        "faith renewal": {"GOLDEN 1:1", "GOLDEN 1:4", "GOLDEN 2:4", "GOLDEN 3:2"},
        "love peace": {"GOLDEN 1:2", "GOLDEN 1:3", "GOLDEN 1:4", "GOLDEN 2:1", "GOLDEN 2:2", "GOLDEN 2:3", "GOLDEN 3:1"},
        "faith peace": {"GOLDEN 1:1", "GOLDEN 1:3", "GOLDEN 1:4", "GOLDEN 2:1", "GOLDEN 2:3", "GOLDEN 2:4", "GOLDEN 3:1"},
        "justice love": {"GOLDEN 1:2", "GOLDEN 1:3", "GOLDEN 1:4", "GOLDEN 2:2", "GOLDEN 2:4", "GOLDEN 3:1"},
        "hope forgiveness": {"GOLDEN 1:1", "GOLDEN 1:2", "GOLDEN 1:4", "GOLDEN 2:1", "GOLDEN 2:3", "GOLDEN 3:2"},
        "peace forgiveness": {"GOLDEN 1:2", "GOLDEN 1:3", "GOLDEN 2:1", "GOLDEN 2:3", "GOLDEN 3:1", "GOLDEN 3:2"},
    }
    comparisons = []
    for query in queries:
        baseline = hybrid_search(
            query, client, "operational-golden-embed", limit=5, db_path=db,
            strategy="legacy", fusion="legacy_weighted",
        )
        candidate = hybrid_search(
            query, client, "operational-golden-embed", limit=5, db_path=db,
            strategy="legacy", fusion="rrf",
        )
        comparison = compare_fusion_rankings(baseline, candidate, limit=5, minimum_overlap=0.70)
        comparisons.append(comparison)
        quality = evaluate_fusion_quality(baseline, candidate, relevance_labels[query], k=5)
        assert quality["overlap_rate"] >= 0.70
        assert quality["max_recall_drop"] == 0.0
        assert quality["max_mrr_drop"] == 0.0

        assert candidate
        for item in candidate:
            normalized = normalize_evidence(item)
            assert normalized.source_type == "scripture"
            assert normalized.source_name == "GOLDEN"
            assert normalized.reference.startswith("GOLDEN ")
            assert item["translation"] == "GOLDEN"
            assert item["language"] == "en"
            assert item["license_note"].startswith("golden-license-")

    assert min(item["overlap_rate"] for item in comparisons) >= 0.70
    assert all(item["approved_for_canary"] for item in comparisons)
    assert any(
        not evaluate_fusion_quality(
            hybrid_search(query, client, "operational-golden-embed", limit=5, db_path=db, strategy="legacy", fusion="legacy_weighted"),
            hybrid_search(query, client, "operational-golden-embed", limit=5, db_path=db, strategy="legacy", fusion="rrf"),
            relevance_labels[query],
        )["approved_for_rollout"]
        for query in queries
    )
    fallback_cases = {
        "reconciliation": 1,
        "unseen-anonymized-token": 0,
    }
    for query, expected_lexical_count in fallback_cases.items():
        lexical = search_passages(query, limit=8, db_path=db)
        assert len(lexical) == expected_lexical_count
        semantic = semantic_search(query, client, "operational-golden-embed", limit=8, db_path=db)
        candidate = rrf_fusion(semantic, lexical[:1], limit=5)
        assert candidate
        for item in candidate:
            normalized = normalize_evidence(item)
            assert normalized.source_type == "scripture"
            assert normalized.source_name == "GOLDEN"
            assert item["license_note"].startswith("golden-license-")
    assert fusion_strategy() == "legacy_weighted"
