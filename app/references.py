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
    # Keep Hangul so Korean Bible names/abbreviations can use the same
    # canonicalization path as English aliases.
    return re.sub(r"[^0-9A-Za-z가-힣]", "", value).upper()


BOOK_ALIASES: dict[str, str] = {}
for row in _BOOKS:
    canonical = row[0]
    for alias in row:
        BOOK_ALIASES[_book_key(alias)] = canonical

# Common Korean Bible names and abbreviations used in sermon workflows.
# These normalize to the same USFM/osis-style three-character codes used by
# the database and the original-language corpora.
_KOREAN_BOOK_ALIASES = {
    "창세기": "GEN", "창": "GEN", "출애굽기": "EXO", "출": "EXO",
    "레위기": "LEV", "레": "LEV", "민수기": "NUM", "민": "NUM",
    "신명기": "DEU", "신": "DEU", "여호수아": "JOS", "수": "JOS",
    "사사기": "JDG", "삿": "JDG", "룻기": "RUT", "룻": "RUT",
    "사무엘상": "1SA", "삼상": "1SA", "사무엘하": "2SA", "삼하": "2SA",
    "열왕기상": "1KI", "왕상": "1KI", "열왕기하": "2KI", "왕하": "2KI",
    "역대상": "1CH", "대상": "1CH", "역대하": "2CH", "대하": "2CH",
    "에스라": "EZR", "스": "EZR", "느헤미야": "NEH", "느": "NEH",
    "에스더": "EST", "에": "EST", "욥기": "JOB", "욥": "JOB",
    "시편": "PSA", "시": "PSA", "잠언": "PRO", "잠": "PRO",
    "전도서": "ECC", "전": "ECC", "아가": "SNG", "아": "SNG",
    "이사야": "ISA", "사": "ISA", "예레미야": "JER", "렘": "JER",
    "예레미야애가": "LAM", "애": "LAM", "에스겔": "EZK", "겔": "EZK",
    "다니엘": "DAN", "단": "DAN", "호세아": "HOS", "호": "HOS",
    "요엘": "JOL", "욜": "JOL", "아모스": "AMO", "암": "AMO",
    "오바댜": "OBA", "옵": "OBA", "요나": "JON", "욘": "JON",
    "미가": "MIC", "미": "MIC", "나훔": "NAM", "나": "NAM",
    "하박국": "HAB", "합": "HAB", "스바냐": "ZEP", "습": "ZEP",
    "학개": "HAG", "학": "HAG", "스가랴": "ZEC", "슥": "ZEC",
    "말라기": "MAL", "말": "MAL",
    "마태복음": "MAT", "마": "MAT", "마가복음": "MRK", "막": "MRK",
    "누가복음": "LUK", "눅": "LUK", "요한복음": "JHN", "요": "JHN",
    "사도행전": "ACT", "행": "ACT", "로마서": "ROM", "롬": "ROM",
    "고린도전서": "1CO", "고전": "1CO", "고린도후서": "2CO", "고후": "2CO",
    "갈라디아서": "GAL", "갈": "GAL", "에베소서": "EPH", "엡": "EPH",
    "빌립보서": "PHP", "빌": "PHP", "골로새서": "COL", "골": "COL",
    "데살로니가전서": "1TH", "살전": "1TH", "데살로니가후서": "2TH", "살후": "2TH",
    "디모데전서": "1TI", "딤전": "1TI", "디모데후서": "2TI", "딤후": "2TI",
    "디도서": "TIT", "딛": "TIT", "빌레몬서": "PHM", "몬": "PHM",
    "히브리서": "HEB", "히": "HEB", "야고보서": "JAS", "약": "JAS",
    "베드로전서": "1PE", "벧전": "1PE", "베드로후서": "2PE", "벧후": "2PE",
    "요한일서": "1JN", "요일": "1JN", "요한이서": "2JN", "요이": "2JN",
    "요한삼서": "3JN", "요삼": "3JN", "유다서": "JUD", "유": "JUD",
    "요한계시록": "REV", "계": "REV",
}
for alias, canonical in _KOREAN_BOOK_ALIASES.items():
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
        raise ValueError("성경 참조는 예: 요 8:32 또는 MAT 14:27-31 형식이어야 합니다.")
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
