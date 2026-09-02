import tempfile
import unittest
from pathlib import Path

from app.morphgnt import import_morphgnt_directory
from app.services.greek_morphology_service import get_greek_tokens, lemma_search


FILES = (
    "61-Mt-morphgnt.txt", "62-Mk-morphgnt.txt", "63-Lk-morphgnt.txt", "64-Jn-morphgnt.txt",
    "65-Ac-morphgnt.txt", "66-Ro-morphgnt.txt", "67-1Co-morphgnt.txt", "68-2Co-morphgnt.txt",
    "69-Ga-morphgnt.txt", "70-Eph-morphgnt.txt", "71-Php-morphgnt.txt", "72-Col-morphgnt.txt",
    "73-1Th-morphgnt.txt", "74-2Th-morphgnt.txt", "75-1Ti-morphgnt.txt", "76-2Ti-morphgnt.txt",
    "77-Tit-morphgnt.txt", "78-Phm-morphgnt.txt", "79-Heb-morphgnt.txt", "80-Jas-morphgnt.txt",
    "81-1Pe-morphgnt.txt", "82-2Pe-morphgnt.txt", "83-1Jn-morphgnt.txt", "84-2Jn-morphgnt.txt",
    "85-3Jn-morphgnt.txt", "86-Jud-morphgnt.txt", "87-Re-morphgnt.txt",
)


class GreekMorphologyServiceTests(unittest.TestCase):
    def test_returns_structured_tokens_and_gap_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "raw"
            root.mkdir()
            sample = "040832 V- 2AAS-S-- ἐλευθερώσει ἐλευθερώσει ἐλευθερώσει ἐλευθερόω\n"
            for name in FILES:
                (root / name).write_text(sample if name == "64-Jn-morphgnt.txt" else "040101 N- ----NSM- Ἐν Ἐν Ἐν ἐν\n", encoding="utf-8")
            db = Path(tmp) / "test.db"
            import_morphgnt_directory(root, db, derived_path=Path(tmp) / "tokens.jsonl")
            result = get_greek_tokens("John 8:32", db)
            self.assertEqual(result["source_status"], "available")
            self.assertEqual(result["tokens"][0]["morphology"]["tense"], "aorist")
            self.assertEqual(get_greek_tokens("JHN 8:1", db)["source_status"], "unavailable_in_source")

    def test_lemma_search_returns_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "raw"
            root.mkdir()
            for name in FILES:
                (root / name).write_text("040101 N- ----NSM- Ἐν Ἐν Ἐν ἐν\n", encoding="utf-8")
            db = Path(tmp) / "test.db"
            import_morphgnt_directory(root, db, derived_path=Path(tmp) / "tokens.jsonl")
            result = lemma_search("ἐν", db_path=db)
            self.assertEqual(result["count"], 1)
            self.assertEqual(result["items"][0]["source"]["version"], "6.12")
