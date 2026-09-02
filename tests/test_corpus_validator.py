import json
import tempfile
import unittest
from pathlib import Path

from app.corpus_validator import validate_sblgnt_corpus
from app.sblgnt import SBLGNT_BOOK_FILENAMES


BOOK_XML = "<book><verse-number id='John 1:1'>1:1</verse-number><w>Ἐν</w></book>"
BOOK_NAMES = {
    "MAT": "Matthew", "MRK": "Mark", "LUK": "Luke", "JHN": "John", "ACT": "Acts", "ROM": "Romans",
    "1CO": "1 Corinthians", "2CO": "2 Corinthians", "GAL": "Galatians", "EPH": "Ephesians", "PHP": "Philippians", "COL": "Colossians",
    "1TH": "1 Thessalonians", "2TH": "2 Thessalonians", "1TI": "1 Timothy", "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon",
    "HEB": "Hebrews", "JAS": "James", "1PE": "1 Peter", "2PE": "2 Peter", "1JN": "1 John", "2JN": "2 John", "3JN": "3 John", "JUD": "Jude", "REV": "Revelation",
}


class CorpusValidatorTests(unittest.TestCase):
    def test_validates_books_and_reports_full_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sblgnt"
            (root / "books").mkdir(parents=True)
            (root / "full").mkdir()
            (root / "metadata").mkdir()
            for code, filename in SBLGNT_BOOK_FILENAMES.items():
                xml = BOOK_XML.replace("John", BOOK_NAMES[code])
                (root / "books" / filename).write_text(xml, encoding="utf-8")
            (root / "full" / "sblgnt.xml").write_text("<sblgnt><license/></sblgnt>", encoding="utf-8")
            metadata = {"source": "SBLGNT", "version": "v1.2", "license": "CC BY 4.0", "source_url": "https://example.test", "files": []}
            (root / "metadata" / "source.json").write_text(json.dumps(metadata), encoding="utf-8")
            result = validate_sblgnt_corpus(root)
            self.assertTrue(result["ok"])
            self.assertEqual(result["books_found"], 27)
            self.assertEqual(result["full"]["status"], "metadata_shell")
            self.assertTrue(any(issue["code"] == "full_has_no_verses" for issue in result["issues"]))

    def test_missing_book_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sblgnt"
            (root / "books").mkdir(parents=True)
            result = validate_sblgnt_corpus(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any(issue["code"] == "book_missing" for issue in result["issues"]))
