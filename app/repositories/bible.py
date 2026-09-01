"""SQLite persistence for Bible translation licensing, independent of app.core."""

from __future__ import annotations

from contextlib import contextmanager
import sqlite3
import re
from pathlib import Path

from app.paths import DATA_DIR
from app.references import expand_reference, normalize_reference, validate_primary_original_language


DB_PATH = DATA_DIR / "bible.db"


@contextmanager
def _connect(*args, **kwargs):
    con = sqlite3.connect(*args, **kwargs)
    try:
        with con:
            yield con
    finally:
        con.close()


def _ensure_translation_license_table(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS translation_licenses (
                   translation TEXT PRIMARY KEY,
                   copyright_holder TEXT NOT NULL DEFAULT '',
                   license_status TEXT NOT NULL,
                   permission_ref TEXT NOT NULL DEFAULT '',
                   source_url TEXT NOT NULL DEFAULT '',
                   allow_fulltext INTEGER NOT NULL DEFAULT 0,
                   notes TEXT NOT NULL DEFAULT ''
               )"""
        )


def _ensure_passage_tables(db_path: Path) -> None:
    """Create only the tables required by passage writes and embedding invalidation."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS passages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                translation TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'ko',
                reference TEXT NOT NULL,
                text TEXT NOT NULL,
                license_note TEXT NOT NULL DEFAULT '',
                UNIQUE(translation, reference)
            );
            CREATE INDEX IF NOT EXISTS idx_passages_reference ON passages(reference);
            CREATE INDEX IF NOT EXISTS idx_passages_translation ON passages(translation);
            CREATE TABLE IF NOT EXISTS rag_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passage_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                vector_json TEXT NOT NULL,
                dimension INTEGER NOT NULL,
                UNIQUE(passage_id, model),
                FOREIGN KEY(passage_id) REFERENCES passages(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_rag_model ON rag_embeddings(model);
            """
        )


def add_passage(
    translation: str,
    language: str,
    reference: str,
    text: str,
    license_note: str = "",
    db_path: Path = DB_PATH,
) -> None:
    """Store one passage and invalidate its existing RAG embeddings."""
    _ensure_translation_license_table(db_path)
    _ensure_passage_tables(db_path)
    with _connect(db_path) as con:
        license_row = con.execute(
            "SELECT allow_fulltext FROM translation_licenses WHERE translation=?", (translation.strip(),)
        ).fetchone()
        if license_row is not None and not bool(license_row[0]):
            raise ValueError(f"{translation.strip()} 번역본은 사용권 등록부에서 전문 저장이 허용되지 않았습니다.")
        con.execute(
            """
            INSERT INTO passages(translation, language, reference, text, license_note)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(translation, reference) DO UPDATE SET
                language=excluded.language,
                text=excluded.text,
                license_note=excluded.license_note
            """,
            (translation.strip(), language.strip(), reference.strip(), text.strip(), license_note.strip()),
        )
        passage_id = con.execute(
            "SELECT id FROM passages WHERE translation=? AND reference=?",
            (translation.strip(), reference.strip()),
        ).fetchone()[0]
        con.execute("DELETE FROM rag_embeddings WHERE passage_id=?", (passage_id,))


def persist_passage_batch(normalized, db_path: Path = DB_PATH) -> int:
    """Upsert a normalized passage batch and invalidate stale RAG vectors atomically."""
    _ensure_passage_tables(db_path)
    with _connect(db_path, timeout=30) as con:
        con.execute("PRAGMA busy_timeout=30000")
        for translation, language, reference, text, license_note in normalized:
            con.execute(
                """
                INSERT INTO passages(translation, language, reference, text, license_note)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(translation, reference) DO UPDATE SET
                    language=excluded.language,
                    text=excluded.text,
                    license_note=excluded.license_note
                """,
                (translation, language, reference, text, license_note),
            )
        con.executemany(
            "DELETE FROM rag_embeddings WHERE passage_id=(SELECT id FROM passages WHERE translation=? AND reference=?)",
            [(row[0], row[2]) for row in normalized],
        )
    return len(normalized)


def delete_bible_translation(translation: str, db_path: Path = DB_PATH) -> dict:
    """Delete one translation and its dependent RAG vectors atomically."""
    _ensure_passage_tables(db_path)
    translation = translation.strip()
    if not translation:
        raise ValueError("삭제할 번역/자료명을 입력하세요.")
    with _connect(db_path) as con:
        passage_ids = [row[0] for row in con.execute(
            "SELECT id FROM passages WHERE translation=?", (translation,)
        )]
        if not passage_ids:
            raise ValueError("삭제할 번역/자료를 찾지 못했습니다.")
        placeholders = ",".join("?" for _ in passage_ids)
        vectors = int(con.execute(
            f"SELECT COUNT(*) FROM rag_embeddings WHERE passage_id IN ({placeholders})", passage_ids
        ).fetchone()[0])
        con.execute(f"DELETE FROM rag_embeddings WHERE passage_id IN ({placeholders})", passage_ids)
        deleted = con.execute("DELETE FROM passages WHERE translation=?", (translation,)).rowcount
    return {"translation": translation, "deleted_passages": int(deleted), "deleted_vectors": vectors}


def search_passages(query: str, limit: int = 24, db_path: Path = DB_PATH) -> list[dict]:
    """Search registered passages by reference or text tokens."""
    _ensure_passage_tables(db_path)
    tokens = [t for t in re.split(r"\s+", query.strip()) if t]
    if not tokens:
        return []
    clauses = []
    params: list[str | int] = []
    for token in tokens[:8]:
        clauses.append("(reference LIKE ? OR text LIKE ?)")
        pattern = f"%{token}%"
        params.extend([pattern, pattern])
    params.append(limit)
    sql = f"""
        SELECT id, translation, language, reference, text, license_note
        FROM passages
        WHERE {' OR '.join(clauses)}
        ORDER BY reference, translation
        LIMIT ?
    """
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute(sql, params)]


def compare_reference(reference: str, db_path: Path = DB_PATH) -> list[dict]:
    """Return registered translations matching a single reference or range."""
    _ensure_passage_tables(db_path)
    if not reference.strip():
        return []
    try:
        wanted = expand_reference(reference)
    except ValueError:
        wanted = []
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        if not wanted:
            rows = con.execute(
                "SELECT translation, language, reference, text, license_note FROM passages WHERE reference = ? ORDER BY language, translation",
                (reference.strip(),),
            )
            return [dict(row) for row in rows]
        rows = [dict(row) for row in con.execute(
            "SELECT translation, language, reference, text, license_note FROM passages"
        )]
    wanted_order = {value: index for index, value in enumerate(wanted)}
    matched = []
    for item in rows:
        try:
            key = normalize_reference(item["reference"])
        except ValueError:
            continue
        if key in wanted_order:
            matched.append((wanted_order[key], item))
    return [item for _, item in sorted(matched, key=lambda pair: (pair[0], pair[1]["language"], pair[1]["translation"]))]


def fetch_original_note_rows(reference: str, db_path: Path = DB_PATH) -> list[dict]:
    """Fetch raw original-language note rows; enrichment remains in the core service."""
    _ensure_original_notes_table(db_path)
    _ensure_original_lexicon_table(db_path)
    try:
        wanted = expand_reference(reference)
    except ValueError:
        wanted = []
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        if not wanted:
            return [dict(row) for row in con.execute(
                """SELECT id, reference, language, lemma, transliteration, gloss, morphology, source, license_note
                   FROM original_word_notes WHERE reference=? ORDER BY language, id""",
                (reference.strip(),),
            )]
        rows = [dict(row) for row in con.execute(
            """SELECT id, reference, language, lemma, transliteration, gloss, morphology, source, license_note
               FROM original_word_notes"""
        )]
    wanted_order = {value: index for index, value in enumerate(wanted)}
    matched = []
    for item in rows:
        try:
            key = normalize_reference(item["reference"])
        except ValueError:
            continue
        if key in wanted_order:
            matched.append((wanted_order[key], item))
    return [item for _, item in sorted(matched, key=lambda pair: (pair[0], pair[1]["language"], pair[1]["id"]))]


def db_stats(db_path: Path = DB_PATH) -> dict:
    """Return basic counts for registered Bible and original-language data."""
    _ensure_passage_tables(db_path)
    _ensure_original_notes_table(db_path)
    _ensure_original_lexicon_table(db_path)
    with _connect(db_path) as con:
        passages = con.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
        translations = con.execute("SELECT COUNT(DISTINCT translation) FROM passages").fetchone()[0]
        languages = con.execute("SELECT COUNT(DISTINCT language) FROM passages").fetchone()[0]
        original_note_count = con.execute("SELECT COUNT(*) FROM original_word_notes").fetchone()[0]
        original_lexicon_count = con.execute("SELECT COUNT(*) FROM original_lexicon").fetchone()[0]
    return {
        "passages": passages, "translations": translations, "languages": languages,
        "original_notes": original_note_count, "original_lexicon": original_lexicon_count,
    }


def fetch_bible_integrity_metrics(db_path: Path = DB_PATH) -> dict:
    """Fetch raw database integrity metrics; issue policy remains in app.core."""
    _ensure_passage_tables(db_path)
    _ensure_translation_license_table(db_path)
    with _connect(db_path) as con:
        quick_check = str(con.execute("PRAGMA quick_check").fetchone()[0])
        blank_passages = int(con.execute(
            "SELECT COUNT(*) FROM passages WHERE TRIM(reference)='' OR TRIM(text)='' OR TRIM(translation)=''"
        ).fetchone()[0])
        orphan_vectors = int(con.execute(
            """SELECT COUNT(*) FROM rag_embeddings e
               LEFT JOIN passages p ON p.id=e.passage_id WHERE p.id IS NULL"""
        ).fetchone()[0])
        blocked_fulltext = int(con.execute(
            """SELECT COUNT(*) FROM passages p JOIN translation_licenses t ON t.translation=p.translation
               WHERE t.allow_fulltext=0"""
        ).fetchone()[0])
    return {
        "quick_check": quick_check,
        "blank_passages": blank_passages,
        "orphan_vectors": orphan_vectors,
        "blocked_fulltext": blocked_fulltext,
    }


def fetch_bible_dashboard_rows(db_path: Path = DB_PATH) -> list[dict]:
    """Fetch translation-level dashboard rows and RAG vector counts."""
    _ensure_passage_tables(db_path)
    _ensure_translation_license_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = [dict(row) for row in con.execute(
            """SELECT p.translation, MIN(p.language) AS language, COUNT(*) AS passages,
                      COUNT(DISTINCT p.reference) AS references_count,
                      SUM(LENGTH(p.text)) AS characters,
                      COALESCE(t.license_status, 'unregistered') AS license_status,
                      COALESCE(t.allow_fulltext, -1) AS allow_fulltext
               FROM passages p
               LEFT JOIN translation_licenses t ON t.translation=p.translation
               GROUP BY p.translation
               ORDER BY p.translation"""
        )]
        vector_counts = {
            row[0]: row[1] for row in con.execute(
                """SELECT p.translation, COUNT(e.id)
                   FROM passages p LEFT JOIN rag_embeddings e ON e.passage_id=p.id
                   GROUP BY p.translation"""
            )
        }
    for row in rows:
        row["rag_vectors"] = int(vector_counts.get(row["translation"], 0))
    return rows


def _ensure_original_notes_table(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS original_word_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference TEXT NOT NULL,
                language TEXT NOT NULL,
                lemma TEXT NOT NULL,
                transliteration TEXT NOT NULL DEFAULT '',
                gloss TEXT NOT NULL DEFAULT '',
                morphology TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                license_note TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_original_reference ON original_word_notes(reference);
            """
        )


def add_original_note(data: dict, db_path: Path = DB_PATH) -> int:
    """Store one validated original-language note and return its row id."""
    _ensure_original_notes_table(db_path)
    try:
        reference = normalize_reference(str(data["reference"]))
    except ValueError:
        reference = str(data["reference"]).strip()
    validate_primary_original_language(reference, str(data.get("language", "")))
    with _connect(db_path) as con:
        cur = con.execute(
            """INSERT INTO original_word_notes(reference, language, lemma, transliteration, gloss, morphology, source, license_note)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
            (reference, str(data["language"]).strip(), str(data["lemma"]).strip(),
             str(data.get("transliteration", "")).strip(), str(data.get("gloss", "")).strip(),
             str(data.get("morphology", "")).strip(), str(data.get("source", "")).strip(),
             str(data.get("license_note", "")).strip()),
        )
        return int(cur.lastrowid)


def _ensure_original_lexicon_table(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS original_lexicon (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                language TEXT NOT NULL,
                lemma TEXT NOT NULL,
                lookup_key TEXT NOT NULL,
                transliteration TEXT NOT NULL DEFAULT '',
                gloss TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                license_note TEXT NOT NULL,
                UNIQUE(language, lookup_key, source)
            );
            CREATE INDEX IF NOT EXISTS idx_original_lexicon_lookup ON original_lexicon(language, lookup_key);
            """
        )


def original_lexicon_stats(db_path: Path = DB_PATH) -> dict:
    """Return total and per-language counts for the registered lexicon."""
    _ensure_original_lexicon_table(db_path)
    with _connect(db_path) as con:
        total = int(con.execute("SELECT COUNT(*) FROM original_lexicon").fetchone()[0])
        rows = con.execute("SELECT language, COUNT(*) FROM original_lexicon GROUP BY language ORDER BY language").fetchall()
    return {"total": total, "languages": {str(language): int(count) for language, count in rows}}


def register_translation_license(data: dict, db_path: Path = DB_PATH) -> None:
    _ensure_translation_license_table(db_path)
    with _connect(db_path) as con:
        con.execute(
            """INSERT INTO translation_licenses(translation, copyright_holder, license_status, permission_ref, source_url, allow_fulltext, notes)
               VALUES(?, ?, ?, ?, ?, ?, ?) ON CONFLICT(translation) DO UPDATE SET
               copyright_holder=excluded.copyright_holder, license_status=excluded.license_status,
               permission_ref=excluded.permission_ref, source_url=excluded.source_url,
               allow_fulltext=excluded.allow_fulltext, notes=excluded.notes""",
            (str(data["translation"]).strip(), str(data.get("copyright_holder", "")).strip(),
             str(data["license_status"]).strip(), str(data.get("permission_ref", "")).strip(),
             str(data.get("source_url", "")).strip(), 1 if data.get("allow_fulltext") else 0,
             str(data.get("notes", "")).strip()),
        )


def translation_licenses(db_path: Path = DB_PATH) -> list[dict]:
    _ensure_translation_license_table(db_path)
    with _connect(db_path) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute("SELECT * FROM translation_licenses ORDER BY translation")]
