import tempfile
import unittest
from pathlib import Path

from app.morphgnt import backfill_greek_pronunciations, import_morphgnt_directory, parse_morphgnt_content
from app.repositories.greek_morphology import get_tokens, search_by_lemma


class MorphGntNormalizedTests(unittest.TestCase):
    def test_parses_raw_forms_and_morphology_without_losing_source_values(self):
        result = parse_morphgnt_content(
            "040832 V- 2AAS-S-- ἐλευθερώσει ἐλευθερώσει ἐλευθερώσει ἐλευθερόω\n",
            "64-Jn-morphgnt.txt", "a" * 64,
        )
        token = result["tokens"][0]
        self.assertEqual(token["book_code"], "JHN")
        self.assertEqual(token["token_index"], 1)
        self.assertEqual(token["pos_raw"], "V-")
        self.assertEqual(token["parsing_raw"], "2AAS-S--")
        self.assertEqual(token["tense"], "aorist")
        self.assertEqual(token["voice"], "active")
        self.assertEqual(token["mood"], "subjunctive")

    def test_import_is_idempotent_and_query_preserves_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "raw"
            root.mkdir()
            sample = "\n".join(["040101 N- ----NSM- Ἐν Ἐν Ἐν ἐν", "040101 N- ----DSF- ἀρχῇ ἀρχῇ ἀρχῇ ἀρχή"])
            for index, name in enumerate((
                "61-Mt-morphgnt.txt", "62-Mk-morphgnt.txt", "63-Lk-morphgnt.txt", "64-Jn-morphgnt.txt",
                "65-Ac-morphgnt.txt", "66-Ro-morphgnt.txt", "67-1Co-morphgnt.txt", "68-2Co-morphgnt.txt",
                "69-Ga-morphgnt.txt", "70-Eph-morphgnt.txt", "71-Php-morphgnt.txt", "72-Col-morphgnt.txt",
                "73-1Th-morphgnt.txt", "74-2Th-morphgnt.txt", "75-1Ti-morphgnt.txt", "76-2Ti-morphgnt.txt",
                "77-Tit-morphgnt.txt", "78-Phm-morphgnt.txt", "79-Heb-morphgnt.txt", "80-Jas-morphgnt.txt",
                "81-1Pe-morphgnt.txt", "82-2Pe-morphgnt.txt", "83-1Jn-morphgnt.txt", "84-2Jn-morphgnt.txt",
                "85-3Jn-morphgnt.txt", "86-Jud-morphgnt.txt", "87-Re-morphgnt.txt",
            )):
                (root / name).write_text(sample if index == 3 else "040101 N- ----NSM- Ἐν Ἐν Ἐν ἐν\n", encoding="utf-8")
            db = Path(tmp) / "test.db"
            first = import_morphgnt_directory(root, db)
            second = import_morphgnt_directory(root, db)
            self.assertEqual(first["rows"], 28)
            self.assertEqual(second["rows"], 28)
            self.assertEqual(len(get_tokens("JHN", 1, 1, db)), 2)
            self.assertEqual(len(search_by_lemma("ἐν", db_path=db)), 1)

    def test_backfill_uses_morphgnt_surface_forms_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            con = __import__("sqlite3").connect(db)
            try:
                con.execute("""CREATE TABLE greek_nt_tokens (
                    book_code TEXT, chapter INTEGER, verse INTEGER, token_index INTEGER,
                    text_form TEXT, lemma TEXT
                )""")
                con.executemany("INSERT INTO greek_nt_tokens VALUES (?, ?, ?, ?, ?, ?)", [
                    ("JHN", 1, 1, 1, "Ἐν", "ἐν"),
                    ("JHN", 1, 1, 2, "ἀρχῇ", "ἀρχή"),
                ])
                con.commit()
            finally:
                con.close()
            first = backfill_greek_pronunciations(db)
            second = backfill_greek_pronunciations(db)
            self.assertEqual(first["processed_tokens"], 2)
            self.assertEqual(first["greek_pronunciation_rows"], 2)
            self.assertEqual(second["greek_pronunciation_rows"], 2)
            con = __import__("sqlite3").connect(db)
            try:
                rows = con.execute("SELECT surface_form, transliteration, source FROM original_pronunciations ORDER BY token_index").fetchall()
            finally:
                con.close()
            self.assertEqual(rows[0][0], "Ἐν")
            self.assertTrue(rows[0][1])
            self.assertEqual(rows[0][2], "MorphGNT SBLGNT")
