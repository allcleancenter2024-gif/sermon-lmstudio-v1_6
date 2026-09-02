import tempfile
import unittest
from pathlib import Path

from app.sblgnt import load_sblgnt_passages, resolve_sblgnt_source


XML = """<book id='Jhn'><p>
<verse-number id='John 8:32'>8:32</verse-number><w>καὶ</w><suffix> </suffix><w>γνώσεσθε</w>
</p><p><verse-number id='John 8:33'>8:33</verse-number><w>ἀπεκρίθησαν</w></p>
</book>"""


class SblgntCatalogTests(unittest.TestCase):
    def test_book_file_is_preferred_for_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sblgnt"
            for name in ("books", "full", "apparatus"):
                (root / name).mkdir(parents=True)
            (root / "books" / "John.xml").write_text(XML, encoding="utf-8")
            (root / "full" / "sblgnt.xml").write_text("<book/>", encoding="utf-8")
            self.assertEqual(resolve_sblgnt_source("JHN 8:32", root), root / "books" / "John.xml")
            result = load_sblgnt_passages("John 8:32", root)
            self.assertEqual(result["source_kind"], "book")
            self.assertEqual([item["reference"] for item in result["items"]], ["JHN 8:32"])

    def test_full_file_is_fallback_when_book_file_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sblgnt"
            (root / "full").mkdir(parents=True)
            (root / "full" / "sblgnt.xml").write_text(XML, encoding="utf-8")
            result = load_sblgnt_passages("JHN 8:32", root)
            self.assertEqual(result["source_kind"], "full")
            self.assertEqual(len(result["items"]), 1)

    def test_missing_source_is_reported_without_fallback_guess(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = load_sblgnt_passages("JHN 8:32", Path(tmp) / "sblgnt")
            self.assertEqual(result["source_kind"], "missing")
            self.assertEqual(result["missing"], ["JHN 8:32"])
