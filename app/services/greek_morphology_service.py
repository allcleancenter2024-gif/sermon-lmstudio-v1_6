"""Read-only service for the normalized MorphGNT layer."""

from __future__ import annotations

from pathlib import Path

from app.references import parse_reference
from app.repositories.greek_morphology import get_tokens, search_by_lemma, search_by_normalized_form


_JOHN_GAP = {("JHN", 8, verse) for verse in range(1, 12)}


def _token_response(token: dict) -> dict:
    return {
        "text": token["text_form"],
        "word": token["word_form"],
        "normalized": token["normalized_form"],
        "lemma": token["lemma"],
        "pos": token["pos_raw"],
        "parsing_raw": token["parsing_raw"],
        "morphology": {
            "person": token["person"], "tense": token["tense"], "voice": token["voice"],
            "mood": token["mood"], "case": token["grammatical_case"],
            "number": token["grammatical_number"], "gender": token["gender"], "degree": token["degree"],
        },
        "token_index": token["token_index"],
        "source": {"name": token["source_name"], "version": token["source_version"], "file": token["source_file"], "sha256": token["source_sha256"]},
        "validation_status": token["validation_status"],
    }


def get_greek_tokens(reference: str, db_path: Path | None = None) -> dict:
    parsed = parse_reference(reference)
    if parsed.start_verse != parsed.end_verse:
        raise ValueError("헬라어 형태론 조회 API는 한 절씩 조회해야 합니다.")
    rows = get_tokens(parsed.book, parsed.chapter, parsed.start_verse, db_path) if db_path else get_tokens(parsed.book, parsed.chapter, parsed.start_verse)
    gap = (parsed.book, parsed.chapter, parsed.start_verse) in _JOHN_GAP
    return {
        "reference": f"{parsed.book}.{parsed.chapter}.{parsed.start_verse}",
        "display_reference": f"{parsed.book} {parsed.chapter}:{parsed.start_verse}",
        "source_status": "available" if rows else "unavailable_in_source" if gap else "not_imported",
        "tokens": [_token_response(row) for row in rows],
    }


def lemma_search(lemma: str, limit: int = 50, db_path: Path | None = None) -> dict:
    value = str(lemma or "").strip()
    if not value:
        raise ValueError("검색할 lemma를 입력하세요.")
    rows = search_by_lemma(value, limit=limit, db_path=db_path) if db_path else search_by_lemma(value, limit=limit)
    return {"query": value, "count": len(rows), "items": [_token_response(row) for row in rows]}


def normalized_search(word: str, limit: int = 50, db_path: Path | None = None) -> dict:
    value = str(word or "").strip()
    if not value:
        raise ValueError("검색할 정규화 단어를 입력하세요.")
    rows = search_by_normalized_form(value, limit=limit, db_path=db_path) if db_path else search_by_normalized_form(value, limit=limit)
    return {"query": value, "count": len(rows), "items": [_token_response(row) for row in rows]}
