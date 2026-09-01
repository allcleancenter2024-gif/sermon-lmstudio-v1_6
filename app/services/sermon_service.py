"""Sermon generation workflow orchestration.

This module coordinates generation and post-generation validation while keeping
database persistence, provider HTTP, RAG, grounding, and prompt implementations
in their existing modules.
"""
import os

from app.core import (
    analyze_citations,
    build_post_generation_quality,
    build_resize_prompt,
    build_sermon_prompt,
    create_generation_audit,
    estimate_minutes,
    validate_quotes,
)
from app.grounding.audit import audit_sermon


def generate_sermon_workflow(
    data,
    *,
    client,
    passages,
    word_notes,
    doctrine_notes,
    web_evidence=None,
    web_grounding_meta=None,
    search_mode,
    reading_cpm,
    clean_outline,
    select_generation_model,
):
    """Run the existing generation/resize/validation/audit sequence.

    The callable ``select_generation_model`` is injected from the API layer so
    this Service does not import ``app.main`` or own Router concerns.
    """
    model, _ = select_generation_model(client, data.model)
    prompt_payload = data.model_dump()
    prompt_payload["reading_cpm"] = reading_cpm
    prompt_payload["outline"] = clean_outline
    web_evidence = list(web_evidence or [])
    doctrine_prompt_notes = list(doctrine_notes or []) + [item.as_dict() if hasattr(item, "as_dict") else item for item in web_evidence]
    system, user = build_sermon_prompt(prompt_payload, passages, word_notes, doctrine_prompt_notes)
    try:
        sermon = client.chat(model, system, user)
    except ConnectionError as exc:
        if "컨텍스트 한도 초과" not in str(exc):
            raise
        prompt_payload["_context_compact_level"] = 2
        system, user = build_sermon_prompt(prompt_payload, passages, word_notes, doctrine_prompt_notes)
        sermon = client.chat(model, system, user)

    resize_count = 0
    while passages and resize_count < 2 and abs(estimate_minutes(sermon, reading_cpm) - data.minutes) / data.minutes > 0.10:
        resize_system, resize_user = build_resize_prompt(sermon, data.minutes, passages, reading_cpm)
        sermon = client.chat(model, resize_system, resize_user, temperature=0.15)
        resize_count += 1

    unchecked_refs = validate_quotes(sermon, passages)
    minutes_estimate = estimate_minutes(sermon, reading_cpm)
    citation_analysis = analyze_citations(sermon, passages)
    post_generation_quality = build_post_generation_quality(
        sermon=sermon,
        passages=passages,
        word_notes=word_notes,
        doctrine_notes=doctrine_notes,
        target_minutes=data.minutes,
        actual_minutes=minutes_estimate,
        citation_analysis=citation_analysis,
    )
    audit = create_generation_audit(
        model=model,
        embedding_model=data.embedding_model,
        search_mode=search_mode,
        target_minutes=data.minutes,
        actual_minutes=minutes_estimate,
        passages=passages,
        unchecked=unchecked_refs,
        word_notes=word_notes,
        doctrine_notes=doctrine_notes,
        citation_analysis=citation_analysis,
        post_generation_quality=post_generation_quality,
    )
    result = {
        "sermon": sermon,
        "model": model,
        "minutes_estimate": minutes_estimate,
        "duration_adjusted": bool(resize_count),
        "duration_adjustments": resize_count,
        "reading_cpm": reading_cpm,
        "source_count": len(passages),
        "search_mode": search_mode,
        "unchecked_references": unchecked_refs,
        "sources": passages,
        "original_notes": word_notes,
        "doctrine_sources": doctrine_notes,
        "audit_id": audit["id"],
        "audit": audit,
        "citation_analysis": citation_analysis,
        "post_generation_quality": post_generation_quality,
    }
    if web_grounding_meta and web_grounding_meta.get("enabled"):
        result["web_grounding"] = {**web_grounding_meta, "evidence": [item.as_dict() if hasattr(item, "as_dict") else item for item in web_evidence]}
    if os.getenv("GROUNDING_AUDIT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        packet = list(passages) + list(word_notes) + list(doctrine_notes) + [item.as_dict() if hasattr(item, "as_dict") else item for item in web_evidence]
        result["grounding_audit"] = audit_sermon(sermon, packet).as_dict()
    return result
