import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.migrations import deduplicate_oshb_originals


class OshbDeduplicationTests(unittest.TestCase):
    def test_removes_only_duplicate_oshb_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bible.db"
            with closing(sqlite3.connect(path)) as con, con:
                con.executescript("""
                    CREATE TABLE original_word_notes (
                        id INTEGER PRIMARY KEY, reference TEXT, language TEXT, lemma TEXT,
                        morphology TEXT, source TEXT, license_note TEXT,
                        transliteration TEXT DEFAULT '', gloss TEXT DEFAULT ''
                    );
                    CREATE TABLE original_pronunciations (
                        id INTEGER PRIMARY KEY, reference TEXT, language TEXT, lemma TEXT,
                        surface_form TEXT, token_index INTEGER, transliteration TEXT,
                        pronunciation_scheme TEXT, source TEXT, license_note TEXT
                    );
                """)
                con.executemany("INSERT INTO original_word_notes VALUES(?,?,?,?,?,?,?,?,?)", [
                    (1, "ISA 1:1", "he", "1", "H", "Open Scriptures Hebrew Bible (OSHB) v2.2", "URL", "", ""),
                    (2, "ISA 1:1", "he", "1", "H", "OSHB v2.2 · Open Scriptures Hebrew Bible", "new", "", ""),
                    (3, "ISA 1:1", "he", "1", "H2", "other source", "other", "", ""),
                ])
                con.executemany("INSERT INTO original_pronunciations VALUES(?,?,?,?,?,?,?,?,?,?)", [
                    (1, "ISA 1:1", "he", "1", "א", 1, "ʾa", "scheme", "Open Scriptures Hebrew Bible (OSHB) v2.2", "URL"),
                    (2, "ISA 1:1", "he", "1", "א", 1, "ʾa", "scheme", "OSHB v2.2 · Open Scriptures Hebrew Bible", "new"),
                ])
            result = deduplicate_oshb_originals(path)
            self.assertEqual(result["notes_removed"], 1)
            self.assertEqual(result["pronunciations_removed"], 1)
            with closing(sqlite3.connect(path)) as con, con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM original_word_notes").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM original_pronunciations").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
