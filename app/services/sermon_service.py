"""Sermon generation workflow orchestration.

This module coordinates generation and post-generation validation while keeping
database persistence, provider HTTP, RAG, grounding, and prompt implementations
in their existing modules.
"""
import os

from app.core import (
    analyze_citations,
    build_post_generation_quality,
    build_continuation_prompt,
    build_resize_prompt,
    build_sermon_prompt,
    create_generation_audit,
    estimate_minutes,
    validate_quotes,
)
from app.grounding.audit import audit_sermon
from app.grounding.trace import build_evidence_trace
from app.media_prompts import build_media_prompt_packet


def _sermon_max_tokens(target_minutes: int, model: str = "") -> int:
    """Keep local-model generation bounded while scaling with sermon length."""
    if "qwen3" in str(model or "").lower():
        # Qwen3 can be slower on long Korean completions, but a fixed 512-token
        # cap produces an unusably short draft for a 15-minute sermon. Scale
        # the first pass with the requested duration while keeping local
        # inference bounded. The separate auto-resize pass remains disabled for
        # Qwen3 to avoid a second long rewrite request.
        return max(1024, min(3072, int(target_minutes) * 200))
    return max(2048, min(4096, int(target_minutes) * 200))


def _resize_max_tokens(target_minutes: int) -> int:
    """A resize is a correction pass, so it needs less output budget."""
    return max(384, min(600, int(target_minutes) * 40))


def _continuation_max_tokens(target_minutes: int) -> int:
    """Bound the single Qwen3 continuation pass."""
    return max(768, min(1536, int(target_minutes) * 100))


def _should_auto_resize(model: str) -> bool:
    """Qwen3 may spend excessive time rewriting an already complete sermon."""
    return "qwen3" not in str(model or "").lower()


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
        sermon = client.chat(model, system, user, max_tokens=_sermon_max_tokens(data.minutes, model))
    except ConnectionError as exc:
        if "컨텍스트 한도 초과" not in str(exc):
            raise
        prompt_payload["_context_compact_level"] = 2
        system, user = build_sermon_prompt(prompt_payload, passages, word_notes, doctrine_prompt_notes)
        sermon = client.chat(model, system, user, max_tokens=_sermon_max_tokens(data.minutes, model))

    resize_count = 0
    continuation_count = 0
    if "qwen3" in str(model or "").lower():
        initial_minutes = estimate_minutes(sermon, reading_cpm)
        if initial_minutes < data.minutes * 0.90:
            continuation_system, continuation_user = build_continuation_prompt(
                sermon, data.minutes, passages, word_notes, reading_cpm
            )
            continuation = client.chat(
                model,
                continuation_system,
                continuation_user,
                temperature=0.25,
                max_tokens=_continuation_max_tokens(data.minutes),
            ).strip()
            if continuation:
                sermon = f"{sermon.rstrip()}\n\n{continuation}"
                continuation_count = 1
    # Keep one bounded correction pass. Multiple long local-model correction
    # calls can otherwise leave the UI waiting even after the first sermon is
    # already complete.
    while passages and _should_auto_resize(model) and resize_count < 1 and abs(estimate_minutes(sermon, reading_cpm) - data.minutes) / data.minutes > 0.10:
        resize_system, resize_user = build_resize_prompt(sermon, data.minutes, passages, reading_cpm)
        sermon = client.chat(
            model,
            resize_system,
            resize_user,
            temperature=0.15,
            max_tokens=_resize_max_tokens(data.minutes),
        )
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
    evidence_trace = build_evidence_trace(
        sermon,
        list(passages) + list(word_notes) + list(doctrine_notes)
        + [item.as_dict() if hasattr(item, "as_dict") else item for item in web_evidence],
    )
    result = {
        "sermon": sermon,
        "model": model,
        "minutes_estimate": minutes_estimate,
        "duration_adjusted": bool(resize_count),
        "duration_adjustments": resize_count,
        "continuation_count": continuation_count,
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
        "media_prompts": build_media_prompt_packet(sermon, passages, word_notes, doctrine_notes),
        "evidence_snapshot": evidence_trace["snapshot"],
        "sermon_claims": evidence_trace["claims"],
        "citation_links": evidence_trace["citation_links"],
        "citation_trace_validation": evidence_trace["validation"],
    }
    if web_grounding_meta and web_grounding_meta.get("enabled"):
        result["web_grounding"] = {**web_grounding_meta, "evidence": [item.as_dict() if hasattr(item, "as_dict") else item for item in web_evidence]}
    if os.getenv("GROUNDING_AUDIT_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        packet = list(passages) + list(word_notes) + list(doctrine_notes) + [item.as_dict() if hasattr(item, "as_dict") else item for item in web_evidence]
        result["grounding_audit"] = audit_sermon(sermon, packet).as_dict()
    return result
