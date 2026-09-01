"""Pure lexical/semantic result fusion helpers."""
from __future__ import annotations
import os

from app.repositories.bible import search_passages
from app.rag.semantic import semantic_search
from app.rag.fts import fts_search, lexical_strategy


def fuse_hybrid_results(semantic: list[dict], lexical: list[dict], limit: int = 32) -> list[dict]:
    """Fuse semantic and lexical rows using the existing weighted-rank policy."""
    scores: dict[int, tuple[float, dict]] = {}
    for rank, item in enumerate(semantic):
        scores[item["id"]] = (0.75 * max(float(item.get("semantic_score", 0)), 0), item)
    for rank, item in enumerate(lexical):
        lexical_score = 0.25 * (1 - rank / max(len(lexical), 1))
        current, _ = scores.get(item["id"], (0.0, item))
        scores[item["id"]] = (current + lexical_score, item)
    ranked = sorted(scores.values(), key=lambda pair: pair[0], reverse=True)[:limit]
    result = []
    for score, item in ranked:
        clean = dict(item)
        clean["rag_score"] = round(score, 4)
        result.append(clean)
    return result


def rrf_fusion(semantic: list[dict], lexical: list[dict], limit: int = 32, k: int = 60) -> list[dict]:
    """Fuse ranked result lists using Reciprocal Rank Fusion."""
    merged: dict[int, dict] = {}
    for rank, item in enumerate(semantic, start=1):
        key = item["id"]
        row = merged.setdefault(key, dict(item))
        row["semantic_rank"] = rank
        row["rrf_score"] = row.get("rrf_score", 0.0) + 1.0 / (k + rank)
    for rank, item in enumerate(lexical, start=1):
        key = item["id"]
        row = merged.setdefault(key, dict(item))
        row["lexical_rank"] = rank
        row["rrf_score"] = row.get("rrf_score", 0.0) + 1.0 / (k + rank)
    ranked = sorted(merged.values(), key=lambda row: (-row["rrf_score"], row["id"]))[:limit]
    for row in ranked:
        row["rrf_score"] = round(row["rrf_score"], 8)
        row["fusion_strategy"] = "rrf"
    return ranked


def fusion_strategy() -> str:
    value = os.getenv("RAG_FUSION_STRATEGY", "legacy_weighted").strip().lower()
    return value if value in {"legacy_weighted", "rrf"} else "legacy_weighted"


def filter_related_candidates(candidates: list[dict], reference: str, limit: int) -> list[dict]:
    """Exclude the base reference and duplicate references while preserving order."""
    seen = {reference.strip()}
    result = []
    for item in candidates:
        ref = item["reference"].strip()
        if ref in seen:
            continue
        seen.add(ref)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def hybrid_search(query: str, client, model: str, limit: int = 32, db_path=None, strategy: str | None = None, fusion: str | None = None) -> list[dict]:
    """Preserve the existing lexical + 75/25 semantic weighted merge."""
    selected = (strategy or lexical_strategy()).strip().lower()
    if selected == "fts5":
        lexical = fts_search(query, limit=limit, db_path=db_path) if db_path is not None else fts_search(query, limit=limit)
    else:
        lexical = search_passages(query, limit=limit, db_path=db_path) if db_path is not None else search_passages(query, limit=limit)
    semantic = semantic_search(query, client, model, limit=limit, db_path=db_path)
    selected_fusion = (fusion or fusion_strategy()).strip().lower()
    if selected_fusion == "rrf":
        return rrf_fusion(semantic, lexical, limit)
    return fuse_hybrid_results(semantic, lexical, limit)
