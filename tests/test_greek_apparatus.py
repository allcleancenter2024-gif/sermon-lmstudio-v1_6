import tempfile
import unittest
from pathlib import Path

from app.apparatus import import_apparatus_directory, load_apparatus, parse_apparatus_content
from app.repositories.textual_apparatus import get_variants
from app.services.textual_apparatus_service import get_apparatus_notes


SAMPLE = """<book>
<book-name>ΚΑΤΑ ΙΩΑΝΝΗΝ</book-name>
<verse>John 1:15</verse>
<note>1:15 ὃν εἶπον Treg NA28 RP ] ὁ εἰπών WH</note>
<verse>John 1:16</verse>
<note>16 ὅτι WH Treg NA28 ] Καὶ RP</note>
</book>"""


class GreekApparatusTests(unittest.TestCase):
    def test_parser_preserves_notes_and_source_metadata(self):
        items = parse_apparatus_content(SAMPLE, "John.xml", "abc123")
        self.assertEqual([item["reference"] for item in items], ["JHN 1:15", "JHN 1:16"])
        self.assertIn("Treg", items[0]["note"])
        self.assertEqual(items[0]["source"]["name"], "SBLGNT Apparatus")
        self.assertEqual(items[0]["validation_status"], "source_note_only")

    def test_rejects_external_dtd_or_entity(self):
        with self.assertRaises(ValueError):
            parse_apparatus_content('<!DOCTYPE book [<!ENTITY x SYSTEM "file:///secret">]><book/>')

    def test_loads_book_file_without_merging_into_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sblgnt"
            (root / "apparatus").mkdir(parents=True)
            (root / "apparatus" / "John.xml").write_text(SAMPLE, encoding="utf-8")
            result = load_apparatus("JHN 1:15", root)
            self.assertEqual(result["source_status"], "available")
            self.assertEqual(len(result["items"]), 1)
            self.assertEqual(result["items"][0]["reference"], "JHN 1:15")
            self.assertTrue(result["source"]["sha256"])

    def test_missing_apparatus_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = load_apparatus("JHN 1:15", Path(tmp))
            self.assertEqual(result["source_status"], "not_installed")
            self.assertEqual(result["items"], [])

    def test_import_is_separate_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "apparatus"
            root.mkdir()
            for filename in ("John.xml",):
                (root / filename).write_text(SAMPLE, encoding="utf-8")
            # Complete the catalog with valid empty book documents for this importer test.
            from app.sblgnt import SBLGNT_BOOK_FILENAMES
            for filename in set(SBLGNT_BOOK_FILENAMES.values()) - {"John.xml"}:
                (root / filename).write_text("<book/>", encoding="utf-8")
            db = Path(tmp) / "test.db"
            first = import_apparatus_directory(root, db)
            second = import_apparatus_directory(root, db)
            self.assertEqual(first["notes"], 2)
            self.assertEqual(second["database_changes"], 2)
            self.assertEqual(len(get_variants("JHN", 1, 15, db)), 1)
            self.assertEqual(get_apparatus_notes("JHN 1:15", db_path=db)["source_status"], "available")
