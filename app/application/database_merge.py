"""Safe, additive merge for reference data between compatible SQLite databases.

This module deliberately does not restore a database file or copy project-only
tables.  It creates a backup of the target first, inserts only missing rows,
and leaves conflicting target rows untouched.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from app.backup import BackupError, create_backup


REFERENCE_TABLES = (
    "passages",
    "original_word_notes",
    "original_lexicon",
    "original_pronunciations",
)
SKIPPED_TABLES = (
    "rag_embeddings",
    "greek_nt_tokens",
    "greek_nt_verses",
    "textual_variants",
    "kmc_reference_baselines",
    "kmc_reference_check_logs",
    "kmc_reference_review_decisions",
)


class DatabaseMergeError(ValueError):
    """Raised when an additive merge cannot be performed safely."""


def _tables(con: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _count(con: sqlite3.Connection, table: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _require_tables(con: sqlite3.Connection, path: Path, required: set[str]) -> None:
    missing = sorted(required - _tables(con))
    if missing:
        raise DatabaseMergeError(f"{path}에 필요한 테이블이 없습니다: {', '.join(missing)}")


def _insert_passages(source: sqlite3.Connection, target: sqlite3.Connection) -> dict[str, int]:
    rows = source.execute(
        "SELECT translation, language, reference, text, license_note FROM passages"
    ).fetchall()
    imported = conflicts = 0
    for row in rows:
        existing = target.execute(
            "SELECT text, language, license_note FROM passages WHERE translation=? AND reference=?",
            (row[0], row[2]),
        ).fetchone()
        if existing is not None:
            if tuple(existing) != (row[3], row[1], row[4]):
                conflicts += 1
            continue
        target.execute(
            "INSERT INTO passages(translation, language, reference, text, license_note) VALUES(?,?,?,?,?)",
            tuple(row),
        )
        imported += 1
    return {"source": len(rows), "imported": imported, "conflicts": conflicts}


def _insert_unique_table(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
    key_columns: tuple[str, ...],
) -> dict[str, int]:
    rows = source.execute(
        f"SELECT {', '.join(columns)} FROM {table}"
    ).fetchall()
    imported = conflicts = 0
    select = (
        f"SELECT {', '.join(columns)} FROM {table} WHERE "
        + " AND ".join(f"{column}=?" for column in key_columns)
    )
    insert = f"INSERT INTO {table}({', '.join(columns)}) VALUES({','.join('?' for _ in columns)})"
    key_indexes = [columns.index(column) for column in key_columns]
    for row in rows:
        key = tuple(row[index] for index in key_indexes)
        existing = target.execute(select, key).fetchone()
        if existing is not None:
            if tuple(existing) != tuple(row):
                conflicts += 1
            continue
        target.execute(insert, tuple(row))
        imported += 1
    return {"source": len(rows), "imported": imported, "conflicts": conflicts}


def _insert_exact_table(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    table: str,
    columns: tuple[str, ...],
) -> dict[str, int]:
    rows = source.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    if _count(target, table):
        raise DatabaseMergeError(
            f"{table} 대상 DB에 기존 자료가 있어 자동 병합하지 않습니다. "
            "중복 기준을 검토한 뒤 별도 가져오기를 사용하세요."
        )
    insert = f"INSERT INTO {table}({', '.join(columns)}) VALUES({','.join('?' for _ in columns)})"
    target.executemany(insert, [tuple(row) for row in rows])
    return {"source": len(rows), "imported": len(rows), "conflicts": 0}


def merge_reference_data(
    source_db: Path,
    target_db: Path,
    backups_dir: Path,
    app_version: str,
) -> dict[str, Any]:
    """Merge source reference rows into target without overwriting target data.

    A pre-merge backup is mandatory.  Project-only schema tables and embeddings
    are reported as skipped because importing them without a migration and
    passage-id mapping could silently corrupt search behavior.
    """
    source_db, target_db, backups_dir = (
        Path(source_db).resolve(), Path(target_db).resolve(), Path(backups_dir).resolve()
    )
    if source_db == target_db:
        raise DatabaseMergeError("source와 target DB는 같을 수 없습니다.")
    if not source_db.is_file() or not target_db.is_file():
        raise DatabaseMergeError("source와 target DB가 모두 존재해야 합니다.")

    try:
        backup = create_backup(target_db, backups_dir, app_version, reason="pre_merge")
    except BackupError as exc:
        raise DatabaseMergeError(f"병합 전 대상 DB 백업 실패: {exc}") from exc

    stats: dict[str, Any] = {
        "source_db": str(source_db),
        "target_db": str(target_db),
        "backup": backup,
        "tables": {},
        "skipped_tables": list(SKIPPED_TABLES),
        "license_registry": "not_synthesized",
        "rolled_back": False,
    }
    try:
        with closing(sqlite3.connect(f"file:{source_db.as_posix()}?mode=ro", uri=True)) as source, closing(
            sqlite3.connect(target_db)
        ) as target:
            source.row_factory = sqlite3.Row
            target.row_factory = sqlite3.Row
            _require_tables(source, source_db, set(REFERENCE_TABLES))
            _require_tables(target, target_db, set(REFERENCE_TABLES))
            target.execute("PRAGMA foreign_keys=ON")
            target.execute("BEGIN")
            stats["tables"]["passages"] = _insert_passages(source, target)
            stats["tables"]["original_word_notes"] = _insert_exact_table(
                source,
                target,
                "original_word_notes",
                ("reference", "language", "lemma", "transliteration", "gloss", "morphology", "source", "license_note"),
            )
            stats["tables"]["original_lexicon"] = _insert_unique_table(
                source,
                target,
                "original_lexicon",
                ("language", "lemma", "lookup_key", "transliteration", "gloss", "source", "license_note"),
                ("language", "lookup_key", "source"),
            )
            stats["tables"]["original_pronunciations"] = _insert_unique_table(
                source,
                target,
                "original_pronunciations",
                ("reference", "language", "lemma", "surface_form", "token_index", "transliteration", "pronunciation_scheme", "pronunciation_source", "source", "license_note"),
                ("source", "reference", "language", "token_index"),
            )
            target.commit()
    except Exception:
        stats["rolled_back"] = True
        raise
    return stats


__all__ = ["DatabaseMergeError", "REFERENCE_TABLES", "SKIPPED_TABLES", "merge_reference_data"]
