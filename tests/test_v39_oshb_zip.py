import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from app import main
from app.core import import_original_note_batches, original_notes
from app.importers import iter_oshb_zip_original_files


OSHB_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace">
  <osisText>
    <verse osisID="Gen.1.1">
      <w lemma="7225" morph="HNcfsa">ראשית</w>
      <w lemma="430" morph="HNcmpa">אלהים</w>
    </verse>
  </osisText>
</osis>
"""


def make_zip(name="morphhb/wlc/Gen.xml", content=OSHB_XML):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, content)
    return buffer.getvalue()


class V39OshbZipTests(unittest.TestCase):
    def test_current_version(self):
        self.assertEqual(main.APP_VERSION, "40.9.10")

    def test_reads_wlc_xml_from_distribution_zip(self):
        books = list(iter_oshb_zip_original_files(make_zip()))
        self.assertEqual(len(books), 1)
        self.assertEqual(books[0][0], "morphhb/wlc/Gen.xml")
        self.assertEqual(len(books[0][1]), 2)
        self.assertEqual(books[0][1][0]["reference"], "GEN 1:1")
        self.assertEqual(books[0][1][0]["language"], "he")

    def test_rejects_zip_without_wlc_books(self):
        with self.assertRaisesRegex(ValueError, r"wlc/\*\.xml"):
            list(iter_oshb_zip_original_files(make_zip("docs/readme.xml", "<x/>")))

    def test_rejects_zip_path_traversal(self):
        with self.assertRaisesRegex(ValueError, "안전하지"):
            list(iter_oshb_zip_original_files(make_zip("../wlc/Gen.xml")))

    def test_book_batches_are_idempotent(self):
        books = list(iter_oshb_zip_original_files(make_zip()))
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "bible.db"
            first = import_original_note_batches(
                (items for _, items in books), "OSHB test", "CC BY 4.0", db_path
            )
            second = import_original_note_batches(
                (items for _, items in books), "OSHB test", "CC BY 4.0", db_path
            )
            self.assertEqual(first["imported"], 2)
            self.assertEqual(second["imported"], 0)
            self.assertEqual(second["skipped_existing"], 2)
            self.assertEqual(len(original_notes("GEN 1:1", db_path)), 2)

    def test_ui_has_direct_zip_route(self):
        html = Path("templates/index.html").read_text(encoding="utf-8")
        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn('value="oshb_zip"', html)
        self.assertIn("/api/import/original-notes/oshb-zip/preview", js)
        self.assertIn("handleLexiconFileChangeRouted", js)


if __name__ == "__main__":
    unittest.main()
