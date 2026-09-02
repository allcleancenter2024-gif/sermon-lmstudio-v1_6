"""MorphGNT parser and SQLite ingestion helpers.

MorphGNT remains a morphology layer. It does not replace the SBLGNT text
source or feed the sermon/RAG pipeline automatically.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from pathlib import Path

from app.paths import DATA_DIR
from app.repositories.bible import DB_PATH, _connect


MORPHGNT_ROOT = DATA_DIR / "bible" / "greek_nt" / "morphgnt" / "raw"
MORPHGNT_VERSION = "6.12"
MORPHGNT_SOURCE = "MorphGNT SBLGNT"
MORPHGNT_REPOSITORY = "https://github.com/morphgnt/sblgnt"
MORPHGNT_BOOKS = (
    "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP", "COL",
    "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE", "2PE", "1JN", "2JN",
    "3JN", "JUD", "REV",
)
MORPHGNT_FILES = tuple(f for f in (
    "61-Mt-morphgnt.txt", "62-Mk-morphgnt.txt", "63-Lk-morphgnt.txt", "64-Jn-morphgnt.txt",
    "65-Ac-morphgnt.txt", "66-Ro-morphgnt.txt", "67-1Co-morphgnt.txt", "68-2Co-morphgnt.txt",
    "69-Ga-morphgnt.txt", "70-Eph-morphgnt.txt", "71-Php-morphgnt.txt", "72-Col-morphgnt.txt",
    "73-1Th-morphgnt.txt", "74-2Th-morphgnt.txt", "75-1Ti-morphgnt.txt", "76-2Ti-morphgnt.txt",
    "77-Tit-morphgnt.txt", "78-Phm-morphgnt.txt", "79-Heb-morphgnt.txt", "80-Jas-morphgnt.txt",
    "81-1Pe-morphgnt.txt", "82-2Pe-morphgnt.txt", "83-1Jn-morphgnt.txt", "84-2Jn-morphgnt.txt",
    "85-3Jn-morphgnt.txt", "86-Jud-morphgnt.txt", "87-Re-morphgnt.txt",
))

_TENSE = {"P": "present", "I": "imperfect", "F": "future", "A": "aorist", "X": "perfect", "Y": "pluperfect"}
_VOICE = {"A": "active", "M": "middle", "P": "passive"}
_MOOD = {"I": "indicative", "D": "imperative", "S": "subjunctive", "O": "optative", "N": "infinitive", "P": "participle"}
_CASE = {"N": "nominative", "G": "genitive", "D": "dative", "A": "accusative", "V": "vocative"}
_NUMBER = {"S": "singular", "P": "plural"}
_GENDER = {"M": "masculine", "F": "feminine", "N": "neuter"}
_DEGREE = {"C": "comparative", "S": "superlative"}


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _decoded(code: str, mapping: dict[str, str], warnings: set[str], label: str) -> str | None:
    if code == "-" or not code:
        return None
    value = mapping.get(code)
    if value is None:
        warnings.add(f"unknown_{label}:{code}")
    return value


def parse_morphgnt_line(line: str, line_no: int, source_file: str, sha256: str) -> dict:
    fields = line.strip().split()
    if len(fields) < 7 or not re.fullmatch(r"\d{6}", fields[0]):
        raise ValueError(f"{source_file}:{line_no}: MorphGNT 행은 7개 필드와 6자리 BCV가 필요합니다.")
    code, pos_raw, parsing_raw = fields[:3]
    book_order, chapter, verse = int(code[:2]), int(code[2:4]), int(code[4:6])
    if not 1 <= book_order <= len(MORPHGNT_BOOKS) or chapter < 1 or verse < 1:
        raise ValueError(f"{source_file}:{line_no}: BCV 범위가 올바르지 않습니다: {code}")
    if len(parsing_raw) != 8:
        raise ValueError(f"{source_file}:{line_no}: parsing code 길이가 올바르지 않습니다: {parsing_raw}")
    warnings: set[str] = set()
    parsed = {
        "person": {"1": "first", "2": "second", "3": "third"}.get(parsing_raw[0]),
        "tense": _decoded(parsing_raw[1], _TENSE, warnings, "tense"),
        "voice": _decoded(parsing_raw[2], _VOICE, warnings, "voice"),
        "mood": _decoded(parsing_raw[3], _MOOD, warnings, "mood"),
        "grammatical_case": _decoded(parsing_raw[4], _CASE, warnings, "case"),
        "grammatical_number": _decoded(parsing_raw[5], _NUMBER, warnings, "number"),
        "gender": _decoded(parsing_raw[6], _GENDER, warnings, "gender"),
        "degree": _decoded(parsing_raw[7], _DEGREE, warnings, "degree"),
    }
    if parsing_raw[0] not in {"-", "1", "2", "3"}:
        warnings.add(f"unknown_person:{parsing_raw[0]}")
    return {
        "source_name": MORPHGNT_SOURCE, "source_version": MORPHGNT_VERSION, "source_file": source_file,
        "source_sha256": sha256, "book_code": MORPHGNT_BOOKS[book_order - 1], "book_order": book_order,
        "chapter": chapter, "verse": verse, "bcv_raw": code, "pos_raw": pos_raw, "parsing_raw": parsing_raw,
        "text_form": _nfc(fields[3]), "word_form": _nfc(fields[4]), "normalized_form": _nfc(fields[5]),
        "lemma": _nfc(" ".join(fields[6:])), "unicode_normalization": "NFC",
        "validation_status": "validated" if not warnings else "validated_with_warnings", "_warnings": sorted(warnings),
        **parsed,
    }


def parse_morphgnt_content(content: str, source_file: str, sha256: str) -> dict:
    if not content.strip():
        raise ValueError(f"{source_file}: 빈 MorphGNT 파일입니다.")
    tokens, warnings = [], set()
    token_indexes: dict[tuple[str, int, int], int] = {}
    for line_no, raw in enumerate(content.lstrip("\ufeff").splitlines(), 1):
        if not raw.strip():
            continue
        item = parse_morphgnt_line(raw, line_no, source_file, sha256)
        key = (item["book_code"], item["chapter"], item["verse"])
        token_indexes[key] = token_indexes.get(key, 0) + 1
        item["token_index"] = token_indexes[key]
        warnings.update(item.pop("_warnings"))
        tokens.append(item)
    if not tokens:
        raise ValueError(f"{source_file}: 유효한 MorphGNT 행이 없습니다.")
    return {"source_file": source_file, "sha256": sha256, "tokens": tokens, "warnings": sorted(warnings), "rows": len(tokens)}


def ensure_greek_nt_token_table(db_path: Path = DB_PATH) -> None:
    with _connect(db_path) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS greek_nt_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_name TEXT NOT NULL, source_version TEXT NOT NULL,
            source_file TEXT NOT NULL, book_code TEXT NOT NULL, book_order INTEGER NOT NULL,
            chapter INTEGER NOT NULL, verse INTEGER NOT NULL, token_index INTEGER NOT NULL, bcv_raw TEXT NOT NULL,
            text_form TEXT NOT NULL, word_form TEXT NOT NULL, normalized_form TEXT NOT NULL, lemma TEXT NOT NULL,
            pos_raw TEXT NOT NULL, parsing_raw TEXT NOT NULL, person TEXT, tense TEXT, voice TEXT, mood TEXT,
            grammatical_case TEXT, grammatical_number TEXT, gender TEXT, degree TEXT,
            unicode_normalization TEXT NOT NULL DEFAULT 'NFC', import_batch_id TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, validation_status TEXT NOT NULL DEFAULT 'validated', created_at TEXT NOT NULL,
            UNIQUE(source_name, source_version, book_code, chapter, verse, token_index)
        )""")
        con.executescript("""CREATE INDEX IF NOT EXISTS idx_greek_nt_reference ON greek_nt_tokens(book_code, chapter, verse);
        CREATE INDEX IF NOT EXISTS idx_greek_nt_lemma ON greek_nt_tokens(lemma);
        CREATE INDEX IF NOT EXISTS idx_greek_nt_normalized ON greek_nt_tokens(normalized_form);
        CREATE INDEX IF NOT EXISTS idx_greek_nt_pos ON greek_nt_tokens(pos_raw);""")


def import_morphgnt_directory(root: Path = MORPHGNT_ROOT, db_path: Path = DB_PATH, derived_path: Path | None = None, persist: bool = True) -> dict:
    root, derived_path = Path(root), derived_path or DATA_DIR / "bible" / "greek" / "derived" / "greek_nt_tokens.jsonl"
    files = sorted(root.glob("*-morphgnt.txt"))
    if {p.name for p in files} != set(MORPHGNT_FILES):
        raise ValueError(f"MorphGNT 27개 파일이 필요합니다. 현재 {len(files)}개가 감지되었습니다.")
    reports, all_tokens, warnings = [], [], set()
    for path in files:
        raw = path.read_bytes()
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path.name}: UTF-8 decode 실패") from exc
        report = parse_morphgnt_content(content, path.name, hashlib.sha256(raw).hexdigest())
        reports.append({"file": path.name, "rows": report["rows"], "sha256": report["sha256"], "warnings": report["warnings"]})
        warnings.update(report["warnings"])
        all_tokens.extend(report["tokens"])
    batch_id = str(uuid.uuid4())
    if not persist:
        gap = [f"JHN 8:{verse}" for verse in range(1, 12) if not any(x["book_code"] == "JHN" and x["chapter"] == 8 and x["verse"] == verse for x in all_tokens)]
        return {"files": len(files), "rows": len(all_tokens), "warnings": sorted(warnings), "reports": reports, "batch_id": None, "derived_path": None, "john_8_gap": gap, "database_changes": 0}
    ensure_greek_nt_token_table(db_path)
    columns = ["source_name", "source_version", "source_file", "book_code", "book_order", "chapter", "verse", "token_index", "bcv_raw", "text_form", "word_form", "normalized_form", "lemma", "pos_raw", "parsing_raw", "person", "tense", "voice", "mood", "grammatical_case", "grammatical_number", "gender", "degree", "unicode_normalization", "import_batch_id", "source_sha256", "validation_status", "created_at"]
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    for item in all_tokens:
        item["import_batch_id"] = batch_id
    values = [tuple(item.get(column) if column != "created_at" else now for column in columns) for item in all_tokens]
    with _connect(db_path) as con:
        con.executemany(f"INSERT INTO greek_nt_tokens ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) ON CONFLICT(source_name,source_version,book_code,chapter,verse,token_index) DO UPDATE SET source_file=excluded.source_file, text_form=excluded.text_form, word_form=excluded.word_form, normalized_form=excluded.normalized_form, lemma=excluded.lemma, pos_raw=excluded.pos_raw, parsing_raw=excluded.parsing_raw, source_sha256=excluded.source_sha256, validation_status=excluded.validation_status", values)
    derived_path.parent.mkdir(parents=True, exist_ok=True)
    with derived_path.open("w", encoding="utf-8") as handle:
        for item in all_tokens:
            handle.write(json.dumps({k: v for k, v in item.items() if k != "_warnings"}, ensure_ascii=False) + "\n")
    gap = [f"JHN 8:{verse}" for verse in range(1, 12) if not any(x["book_code"] == "JHN" and x["chapter"] == 8 and x["verse"] == verse for x in all_tokens)]
    return {"files": len(files), "rows": len(all_tokens), "warnings": sorted(warnings), "reports": reports, "batch_id": batch_id, "derived_path": str(derived_path), "john_8_gap": gap}
