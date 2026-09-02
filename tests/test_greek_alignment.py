import tempfile
import unittest
from pathlib import Path

from app.alignment import align_reference, build_alignment_report, classify_tokens
from app.morphgnt import import_morphgnt_directory


FILES = (
    "61-Mt-morphgnt.txt", "62-Mk-morphgnt.txt", "63-Lk-morphgnt.txt", "64-Jn-morphgnt.txt",
    "65-Ac-morphgnt.txt", "66-Ro-morphgnt.txt", "67-1Co-morphgnt.txt", "68-2Co-morphgnt.txt",
    "69-Ga-morphgnt.txt", "70-Eph-morphgnt.txt", "71-Php-morphgnt.txt", "72-Col-morphgnt.txt",
    "73-1Th-morphgnt.txt", "74-2Th-morphgnt.txt", "75-1Ti-morphgnt.txt", "76-2Ti-morphgnt.txt",
    "77-Tit-morphgnt.txt", "78-Phm-morphgnt.txt", "79-Heb-morphgnt.txt", "80-Jas-morphgnt.txt",
    "81-1Pe-morphgnt.txt", "82-2Pe-morphgnt.txt", "83-1Jn-morphgnt.txt", "84-2Jn-morphgnt.txt",
    "85-3Jn-morphgnt.txt", "86-Jud-morphgnt.txt", "87-Re-morphgnt.txt",
)


class GreekAlignmentTests(unittest.TestCase):
    def test_classification_is_non_destructive(self):
        self.assertEqual(classify_tokens(["ἀλήθειαν,"], ["ἀλήθειαν"]), "NORMALIZATION_ONLY")
        self.assertEqual(classify_tokens(["καὶ", "λόγος"], ["καὶ"]), "TOKENIZATION_DIFFERENCE")
        self.assertEqual(classify_tokens(["λόγος"], ["ἄνθρωπος"]), "TEXT_DIFFERENCE")
        self.assertEqual(classify_tokens([], ["λόγος"]), "UNRESOLVED")

    def test_reference_alignment_reports_punctuation_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sblgnt"
            (root / "books").mkdir(parents=True)
            (root / "books" / "John.xml").write_text(
                "<book><verse-number id='John 8:32'>8:32</verse-number><w>καὶ</w><suffix> </suffix><w>ἀλήθειαν,</w></book>",
                encoding="utf-8",
            )
            morph_root = Path(tmp) / "morph"
            morph_root.mkdir()
            for name in FILES:
                (morph_root / name).write_text("040832 V- 2AAS-S-- καὶ καὶ καί καί\n" if name == "64-Jn-morphgnt.txt" else "040101 N- ----NSM- Ἐν Ἐν Ἐν ἐν\n", encoding="utf-8")
            db = Path(tmp) / "test.db"
            import_morphgnt_directory(morph_root, db, derived_path=Path(tmp) / "tokens.jsonl")
            self.assertEqual(align_reference("JHN 8:32", db, root)["status"], "TOKENIZATION_DIFFERENCE")

    def test_report_writes_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sblgnt"
            (root / "books").mkdir(parents=True)
            for filename in {"John.xml"}:
                (root / "books" / filename).write_text("<book/>", encoding="utf-8")
            db = Path(tmp) / "test.db"
            output = Path(tmp) / "alignment.json"
            report = build_alignment_report(db, root, output)
            self.assertTrue(output.is_file())
            self.assertEqual(sum(report["counts"].values()), report["items"])

