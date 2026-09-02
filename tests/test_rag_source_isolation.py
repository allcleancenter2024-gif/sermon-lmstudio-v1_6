import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.repositories.rag import fetch_rag_passages


class RagSourceIsolationTests(unittest.TestCase):
    def test_rag_passage_source_does_not_include_greek_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            con = sqlite3.connect(db)
            con.executescript("""
                CREATE TABLE passages (id INTEGER PRIMARY KEY, translation TEXT, language TEXT, reference TEXT, text TEXT);
                CREATE TABLE greek_nt_verses (id INTEGER PRIMARY KEY, canonical_reference TEXT, text TEXT);
                CREATE TABLE greek_nt_tokens (id INTEGER PRIMARY KEY, lemma TEXT);
                CREATE TABLE textual_variants (id INTEGER PRIMARY KEY, note TEXT);
                INSERT INTO passages VALUES (1, 'WEB', 'en', 'JHN 8:32', 'The truth');
                INSERT INTO greek_nt_verses VALUES (1, 'JHN 8:32', 'ἀλήθεια');
            """)
            con.commit()
            con.close()
            rows = fetch_rag_passages(db)
            self.assertEqual(rows, [{"id": 1, "translation": "WEB", "language": "en", "reference": "JHN 8:32", "text": "The truth"}])

