import sqlite3
from pathlib import Path

import pytest

from app.application.database_merge import DatabaseMergeError, merge_reference_data
from app.backup import inspect_backup


SCHEMA = """
CREATE TABLE passages (id INTEGER PRIMARY KEY AUTOINCREMENT, translation TEXT NOT NULL, language TEXT NOT NULL, reference TEXT NOT NULL, text TEXT NOT NULL, license_note TEXT NOT NULL DEFAULT '', UNIQUE(translation, reference));
CREATE TABLE rag_embeddings (id INTEGER PRIMARY KEY AUTOINCREMENT, passage_id INTEGER NOT NULL, model TEXT NOT NULL, vector_json TEXT NOT NULL, dimension INTEGER NOT NULL, UNIQUE(passage_id, model));
CREATE TABLE translation_licenses (translation TEXT PRIMARY KEY, copyright_holder TEXT NOT NULL DEFAULT '', license_status TEXT NOT NULL, permission_ref TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '', allow_fulltext INTEGER NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '');
CREATE TABLE sermons (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE sermon_versions (id INTEGER PRIMARY KEY AUTOINCREMENT, sermon_id INTEGER NOT NULL, version_no INTEGER NOT NULL, content TEXT NOT NULL);
CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE original_word_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT NOT NULL, language TEXT NOT NULL, lemma TEXT NOT NULL, transliteration TEXT NOT NULL DEFAULT '', gloss TEXT NOT NULL DEFAULT '', morphology TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '', license_note TEXT NOT NULL DEFAULT '');
CREATE TABLE original_lexicon (id INTEGER PRIMARY KEY AUTOINCREMENT, language TEXT NOT NULL, lemma TEXT NOT NULL, lookup_key TEXT NOT NULL, transliteration TEXT NOT NULL DEFAULT '', gloss TEXT NOT NULL DEFAULT '', source TEXT NOT NULL, license_note TEXT NOT NULL, UNIQUE(language, lookup_key, source));
CREATE TABLE original_pronunciations (id INTEGER PRIMARY KEY AUTOINCREMENT, reference TEXT NOT NULL, language TEXT NOT NULL, lemma TEXT NOT NULL, surface_form TEXT NOT NULL, token_index INTEGER NOT NULL, transliteration TEXT NOT NULL DEFAULT '', pronunciation_scheme TEXT NOT NULL DEFAULT '', pronunciation_source TEXT NOT NULL DEFAULT 'derived from registered surface form', source TEXT NOT NULL DEFAULT '', license_note TEXT NOT NULL DEFAULT '', UNIQUE(source, reference, language, token_index));
"""


def _db(path: Path) -> None:
    with sqlite3.connect(path) as con:
        con.executescript(SCHEMA)


def test_merge_is_additive_and_creates_backup(tmp_path):
    source, target = tmp_path / "source.db", tmp_path / "target.db"
    _db(source)
    _db(target)
    with sqlite3.connect(source) as con:
        con.execute("INSERT INTO passages(translation,language,reference,text,license_note) VALUES('WEB','en','John 1:1','source text','Public Domain')")
        con.execute("INSERT INTO original_word_notes(reference,language,lemma,source) VALUES('John 1:1','grc','logos','test')")
        con.execute("INSERT INTO original_lexicon(language,lemma,lookup_key,source,license_note) VALUES('grc','logos','3056','test','CC0')")
    with sqlite3.connect(target) as con:
        con.execute("INSERT INTO passages(translation,language,reference,text,license_note) VALUES('WEB','en','John 1:1','user text','user')")

    result = merge_reference_data(source, target, tmp_path / "backups", "40.9.11")

    assert result["rolled_back"] is False
    assert result["tables"]["passages"] == {"source": 1, "imported": 0, "conflicts": 1}
    assert result["tables"]["original_word_notes"]["imported"] == 1
    assert result["tables"]["original_lexicon"]["imported"] == 1
    backups = list((tmp_path / "backups").glob("sermon_backup_*.zip"))
    assert len(backups) == 1
    assert inspect_backup(backups[0])["ok"] is True
    with sqlite3.connect(target) as con:
        assert con.execute("SELECT text FROM passages").fetchone()[0] == "user text"
        assert con.execute("SELECT COUNT(*) FROM original_word_notes").fetchone()[0] == 1


def test_merge_refuses_nonempty_unkeyed_notes_without_partial_write(tmp_path):
    source, target = tmp_path / "source.db", tmp_path / "target.db"
    _db(source)
    _db(target)
    with sqlite3.connect(source) as con:
        con.execute("INSERT INTO passages(translation,language,reference,text) VALUES('WEB','en','John 1:1','source')")
        con.execute("INSERT INTO original_word_notes(reference,language,lemma,source) VALUES('John 1:1','grc','logos','source')")
    with sqlite3.connect(target) as con:
        con.execute("INSERT INTO original_word_notes(reference,language,lemma,source) VALUES('Matt 1:1','grc','genesis','user')")

    with pytest.raises(DatabaseMergeError, match="original_word_notes"):
        merge_reference_data(source, target, tmp_path / "backups", "40.9.11")
    with sqlite3.connect(target) as con:
        assert con.execute("SELECT COUNT(*) FROM passages").fetchone()[0] == 0
        assert con.execute("SELECT COUNT(*) FROM original_word_notes").fetchone()[0] == 1
