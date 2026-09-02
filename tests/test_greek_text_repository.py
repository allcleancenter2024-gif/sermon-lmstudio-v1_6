import tempfile
import unittest
from pathlib import Path

from app.repositories.greek_text import get_verses
from app.services.greek_text_service import get_greek_text
from app.sblgnt import SBLGNT_BOOK_FILENAMES, import_sblgnt_books


class GreekTextRepositoryTests(unittest.TestCase):
    def test_imports_book_text_separately_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sblgnt"
            (root / "books").mkdir(parents=True)
            names = {"MAT": "Matthew", "MRK": "Mark", "LUK": "Luke", "JHN": "John", "ACT": "Acts", "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians", "GAL": "Galatians", "EPH": "Ephesians", "PHP": "Philippians", "COL": "Colossians", "1TH": "1 Thessalonians", "2TH": "2 Thessalonians", "1TI": "1 Timothy", "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon", "HEB": "Hebrews", "JAS": "James", "1PE": "1 Peter", "2PE": "2 Peter", "1JN": "1 John", "2JN": "2 John", "3JN": "3 John", "JUD": "Jude", "REV": "Revelation"}
            for code, filename in SBLGNT_BOOK_FILENAMES.items():
                name = names[code]
                verse = "8:32" if code == "JHN" else "1:1"
                (root / "books" / filename).write_text(f"<book><verse-number id='{name} {verse}'>{verse}</verse-number><w>λόγος</w></book>", encoding="utf-8")
            db = Path(tmp) / "test.db"
            first = import_sblgnt_books(root, db)
            second = import_sblgnt_books(root, db)
            self.assertEqual(first["verses"], 27)
            self.assertEqual(second["database_changes"], 27)
            self.assertEqual(len(get_verses("JHN", 8, 32, db)), 1)
            result = get_greek_text("JHN 8:32", db)
            self.assertEqual(result["source_status"], "available")
            self.assertEqual(result["items"][0]["source"]["name"], "SBLGNT")

    def test_missing_text_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(get_greek_text("JHN 8:32", Path(tmp) / "test.db")["source_status"], "not_imported")
