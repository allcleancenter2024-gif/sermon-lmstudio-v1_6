"""Non-destructive SBLGNT ↔ MorphGNT token alignment diagnostics."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from app.morphgnt import MORPHGNT_BOOKS, ensure_greek_nt_token_table
from app.repositories.bible import DB_PATH, _connect
from app.sblgnt import SBLGNT_BOOK_FILENAMES, SBLGNT_ROOT
from app.references import parse_reference
from app.importers import convert_bible_source


ALIGNMENT_STATUSES = {
    "MATCHED", "NORMALIZATION_ONLY", "TOKENIZATION_DIFFERENCE", "TEXT_DIFFERENCE", "UNRESOLVED",
}


def _comparison_token(value: str) -> str:
    value = unicodedata.normalize("NFC", str(value or "")).strip()
    return "".join(char for char in value if unicodedata.category(char)[0] not in {"P", "S"})


def classify_tokens(sblgnt_tokens: list[str], morphgnt_tokens: list[str]) -> str:
    """Classify without changing either source's token values."""
    if not sblgnt_tokens or not morphgnt_tokens:
        return "UNRESOLVED"
    if sblgnt_tokens == morphgnt_tokens:
        return "MATCHED"
    normalized_sblgnt = [_comparison_token(token) for token in sblgnt_tokens]
    normalized_morphgnt = [_comparison_token(token) for token in morphgnt_tokens]
    if len(normalized_sblgnt) != len(normalized_morphgnt):
        return "TOKENIZATION_DIFFERENCE"
    if normalized_sblgnt == normalized_morphgnt:
        return "NORMALIZATION_ONLY"
    return "TEXT_DIFFERENCE"


def _morph_rows(book: str, chapter: int, verse: int, db_path: Path) -> list[dict]:
    ensure_greek_nt_token_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = __import__("sqlite3").Row
        return [dict(row) for row in con.execute(
            "SELECT text_form, word_form, normalized_form, token_index FROM greek_nt_tokens WHERE book_code=? AND chapter=? AND verse=? ORDER BY token_index",
            (book, chapter, verse),
        )]


def align_reference(reference: str, db_path: Path = DB_PATH, root: Path = SBLGNT_ROOT) -> dict:
    parsed = parse_reference(reference)
    if parsed.start_verse != parsed.end_verse:
        raise ValueError("Alignment 조회는 한 절씩 지원합니다.")
    source = Path(root) / "books" / SBLGNT_BOOK_FILENAMES.get(parsed.book, "")
    if not source.is_file():
        return {"reference": f"{parsed.book} {parsed.chapter}:{parsed.start_verse}", "status": "UNRESOLVED", "reason": "sblgnt_source_missing", "sblgnt_tokens": [], "morphgnt_tokens": []}
    _, passages = convert_bible_source(source.read_text(encoding="utf-8-sig"), "sblgnt_xml")
    key = f"{parsed.book} {parsed.chapter}:{parsed.start_verse}"
    passage = next((item for item in passages if item["reference"] == key), None)
    morph_rows = _morph_rows(parsed.book, parsed.chapter, parsed.start_verse, db_path)
    sblgnt_tokens = passage["text"].split() if passage else []
    morph_tokens = [row["text_form"] for row in morph_rows]
    status = classify_tokens(sblgnt_tokens, morph_tokens)
    return {
        "reference": key, "status": status,
        "sblgnt_tokens": sblgnt_tokens, "morphgnt_tokens": morph_tokens,
        "sblgnt_token_count": len(sblgnt_tokens), "morphgnt_token_count": len(morph_tokens),
        "source": {"sblgnt_file": str(source), "morphgnt_source": "MorphGNT SBLGNT"},
        "note": "판정 결과만 기록하며 어느 원본도 자동 수정하지 않습니다.",
    }


def build_alignment_report(db_path: Path = DB_PATH, root: Path = SBLGNT_ROOT, output_path: Path | None = None) -> dict:
    """Build a corpus-wide report from the installed book XML and MorphGNT table."""
    report_items: list[dict] = []
    ensure_greek_nt_token_table(db_path)
    for book in MORPHGNT_BOOKS:
        source = Path(root) / "books" / SBLGNT_BOOK_FILENAMES[book]
        if not source.is_file():
            report_items.append({"book": book, "status": "UNRESOLVED", "reason": "sblgnt_source_missing"})
            continue
        try:
            _, passages = convert_bible_source(source.read_text(encoding="utf-8-sig"), "sblgnt_xml")
        except ValueError as exc:
            report_items.append({"book": book, "status": "UNRESOLVED", "reason": "sblgnt_parse_error", "error": str(exc)})
            continue
        with _connect(db_path) as con:
            con.row_factory = __import__("sqlite3").Row
            rows = con.execute(
                "SELECT chapter,verse,text_form FROM greek_nt_tokens WHERE book_code=? ORDER BY chapter,verse,token_index",
                (book,),
            ).fetchall()
        morph_by_ref: dict[tuple[int, int], list[str]] = {}
        for row in rows:
            morph_by_ref.setdefault((row["chapter"], row["verse"]), []).append(row["text_form"])
        for passage in passages:
            parsed = parse_reference(passage["reference"])
            sblgnt_tokens = passage["text"].split()
            morph_tokens = morph_by_ref.get((parsed.chapter, parsed.start_verse), [])
            report_items.append({
                "reference": passage["reference"], "book": book,
                "status": classify_tokens(sblgnt_tokens, morph_tokens),
                "sblgnt_token_count": len(sblgnt_tokens), "morphgnt_token_count": len(morph_tokens),
            })
    counts = {status: sum(1 for item in report_items if item.get("status") == status) for status in ALIGNMENT_STATUSES}
    report = {"source": "SBLGNT + MorphGNT", "items": len(report_items), "counts": counts, "alignment": report_items, "policy": "diagnostic_only_no_auto_correction"}
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["output_path"] = str(output_path)
    return report
