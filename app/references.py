from __future__ import annotations

import re
from dataclasses import dataclass


_BOOKS = [
    ("GEN", "Genesis", "Gen"), ("EXO", "Exodus", "Exod", "Ex"), ("LEV", "Leviticus", "Lev"),
    ("NUM", "Numbers", "Num"), ("DEU", "Deuteronomy", "Deut", "Dt"), ("JOS", "Joshua", "Josh"),
    ("JDG", "Judges", "Judg"), ("RUT", "Ruth"), ("1SA", "1 Samuel", "1Sam"), ("2SA", "2 Samuel", "2Sam"),
    ("1KI", "1 Kings", "1Kgs"), ("2KI", "2 Kings", "2Kgs"), ("1CH", "1 Chronicles", "1Chr"),
    ("2CH", "2 Chronicles", "2Chr"), ("EZR", "Ezra"), ("NEH", "Nehemiah", "Neh"), ("EST", "Esther", "Est"),
    ("JOB", "Job"), ("PSA", "Psalms", "Psalm", "Ps"), ("PRO", "Proverbs", "Prov"),
    ("ECC", "Ecclesiastes", "Eccl"), ("SNG", "Song of Songs", "Song", "Canticles"), ("ISA", "Isaiah", "Isa"),
    ("JER", "Jeremiah", "Jer"), ("LAM", "Lamentations", "Lam"), ("EZK", "Ezekiel", "Ezek"), ("DAN", "Daniel", "Dan"),
    ("HOS", "Hosea", "Hos"), ("JOL", "Joel"), ("AMO", "Amos"), ("OBA", "Obadiah", "Obad"),
    ("JON", "Jonah"), ("MIC", "Micah", "Mic"), ("NAM", "Nahum", "Nah"), ("HAB", "Habakkuk", "Hab"),
    ("ZEP", "Zephaniah", "Zeph"), ("HAG", "Haggai", "Hag"), ("ZEC", "Zechariah", "Zech"), ("MAL", "Malachi", "Mal"),
    ("MAT", "Matthew", "Matt", "MATT", "Mt"), ("MRK", "Mark", "Mrk", "Mk"), ("LUK", "Luke", "Lk"),
    ("JHN", "John", "Jn"), ("ACT", "Acts"), ("ROM", "Romans", "Rom"), ("1CO", "1 Corinthians", "1Cor"),
    ("2CO", "2 Corinthians", "2Cor"), ("GAL", "Galatians", "Gal"), ("EPH", "Ephesians", "Eph"),
    ("PHP", "Philippians", "Phil", "Php"), ("COL", "Colossians", "Col"), ("1TH", "1 Thessalonians", "1Thess"),
    ("2TH", "2 Thessalonians", "2Thess"), ("1TI", "1 Timothy", "1Tim"), ("2TI", "2 Timothy", "2Tim"),
    ("TIT", "Titus"), ("PHM", "Philemon", "Phlm"), ("HEB", "Hebrews", "Heb"), ("JAS", "James", "Jas"),
    ("1PE", "1 Peter", "1Pet"), ("2PE", "2 Peter", "2Pet"), ("1JN", "1 John", "1Jn"),
    ("2JN", "2 John", "2Jn"), ("3JN", "3 John", "3Jn"), ("JUD", "Jude"), ("REV", "Revelation", "Rev"),
]


def _book_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", value).upper()


BOOK_ALIASES: dict[str, str] = {}
for row in _BOOKS:
    canonical = row[0]
    for alias in row:
        BOOK_ALIASES[_book_key(alias)] = canonical

OT_BOOKS = {row[0] for row in _BOOKS[:39]}
NT_BOOKS = {row[0] for row in _BOOKS[39:]}


@dataclass(frozen=True)
class ReferenceRange:
    book: str
    chapter: int
    start_verse: int
    end_verse: int


def canonical_book(value: str) -> str:
    raw = value.strip()
    return BOOK_ALIASES.get(_book_key(raw), raw.upper())


def parse_reference(reference: str) -> ReferenceRange:
    cleaned = str(reference or "").strip()
    for marker in ("~", "～", "–", "—", "−"):
        cleaned = cleaned.replace(marker, "-")
    match = re.match(r"^(.+?)\s+(\d+)\s*:\s*(\d+)(?:\s*-\s*(?:(\d+)\s*:\s*)?(\d+))?$", cleaned)
    if not match:
        raise ValueError("성경 참조는 예: MAT 14:27 또는 MAT 14:27-31 형식이어야 합니다.")
    book, chapter_text, start_text, end_chapter_text, end_text = match.groups()
    chapter, start = int(chapter_text), int(start_text)
    end_chapter = int(end_chapter_text) if end_chapter_text else chapter
    end = int(end_text) if end_text else start
    if chapter < 1 or start < 1 or end < 1:
        raise ValueError("장과 절 번호는 1 이상이어야 합니다.")
    if end_chapter != chapter:
        raise ValueError("현재 범위 조회는 같은 장 안의 절 범위만 지원합니다.")
    if end < start:
        raise ValueError("범위의 마지막 절이 시작 절보다 작을 수 없습니다.")
    if end - start + 1 > 200:
        raise ValueError("한 번에 조회할 수 있는 범위는 최대 200절입니다.")
    return ReferenceRange(canonical_book(book), chapter, start, end)


def expand_reference(reference: str) -> list[str]:
    parsed = parse_reference(reference)
    return [f"{parsed.book} {parsed.chapter}:{verse}" for verse in range(parsed.start_verse, parsed.end_verse + 1)]


def normalize_reference(reference: str) -> str:
    parsed = parse_reference(reference)
    if parsed.start_verse == parsed.end_verse:
        return f"{parsed.book} {parsed.chapter}:{parsed.start_verse}"
    return f"{parsed.book} {parsed.chapter}:{parsed.start_verse}-{parsed.end_verse}"


def primary_original_language(reference: str) -> str:
    """Return the primary source-language code used by this app for a canonical Bible book."""
    book = parse_reference(reference).book
    if book in NT_BOOKS:
        return "grc"
    if book in OT_BOOKS:
        return "he"
    return ""


def validate_primary_original_language(reference: str, language: str) -> str:
    """Reject an obvious Hebrew/Greek testament mismatch while allowing other scholarly language codes."""
    expected = primary_original_language(reference)
    actual = str(language or "").strip().casefold()
    if expected and actual in {"he", "grc"} and actual != expected:
        label = "헬라어(grc)" if expected == "grc" else "히브리어(he)"
        raise ValueError(f"{normalize_reference(reference)}의 기본 원어 언어는 {label}입니다. 선택 언어를 확인하세요.")
    return expected
