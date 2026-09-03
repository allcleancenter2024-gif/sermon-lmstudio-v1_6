import tempfile
import unittest
from pathlib import Path

from app.core import import_original_note_batches, original_notes
from app.importers import iter_oshb_zip_original_files
from tests.test_v39_oshb_zip import make_zip


class OriginalPronunciationTests(unittest.TestCase):
    def test_surface_form_and_token_position_are_preserved_separately(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "bible.db"
            items = list(iter_oshb_zip_original_files(make_zip()))[0][1]
            result = import_original_note_batches(iter([items]), "OSHB test", "CC BY 4.0", db_path)
            self.assertEqual(result["imported"], 2)
            rows = original_notes("GEN 1:1", db_path)
            self.assertEqual(rows[0]["pronunciations"][0]["surface_form"], "ראשית")
            self.assertTrue(rows[0]["pronunciations"][0]["transliteration"])
            self.assertEqual(rows[0]["pronunciations"][0]["token_index"], 1)

    def test_repeated_lemma_occurrences_do_not_collide(self):
        xml = """<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><verse osisID="Gen.1.1"><w lemma="1" morph="HN">א</w><w lemma="1" morph="HN">ב</w></verse></osis>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "bible.db"
            items = list(iter_oshb_zip_original_files(make_zip(content=xml)))[0][1]
            import_original_note_batches(iter([items]), "OSHB test", "CC BY 4.0", db_path)
            rows = original_notes("GEN 1:1", db_path)
            self.assertEqual(len(rows[0]["pronunciations"]), 2)
            self.assertEqual([p["token_index"] for p in rows[0]["pronunciations"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
