import tempfile
import unittest
from pathlib import Path

from app.core import (
    add_original_note,
    import_original_lexicon,
    lexicon_lookup_key,
    original_lexicon_stats,
    original_notes,
)
from app.importers import convert_lexicon_source


class V33LexiconEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_csv_lexicon_conversion(self):
        resolved, items = convert_lexicon_source(
            "language,lemma,gloss,transliteration\n"
            "grc,θαρσέω,담대하다,tharseo\n",
            "csv",
        )
        self.assertEqual(resolved, "csv")
        self.assertEqual(items[0]["lemma"], "θαρσέω")
        self.assertEqual(items[0]["gloss"], "담대하다")

    def test_lexicon_fills_only_missing_original_fields_and_keeps_provenance(self):
        add_original_note(
            {
                "reference": "MAT 14:27",
                "language": "grc",
                "lemma": "θαρσέω",
                "transliteration": "",
                "gloss": "",
                "morphology": "V-PAM-2S",
                "source": "MorphGNT",
                "license_note": "MorphGNT test license",
            },
            self.db,
        )
        import_original_lexicon(
            [{"language": "grc", "lemma": "θαρσέω", "transliteration": "tharseo", "gloss": "담대하다"}],
            "Licensed Greek Lexicon",
            "lexicon test license",
            self.db,
        )
        note = original_notes("MAT 14:27", self.db)[0]
        self.assertEqual(note["gloss"], "담대하다")
        self.assertEqual(note["transliteration"], "tharseo")
        self.assertEqual(note["source"], "MorphGNT")
        self.assertEqual(note["license_note"], "MorphGNT test license")
        self.assertTrue(note["lexicon_enriched"])
        self.assertEqual(note["lexicon_source"], "Licensed Greek Lexicon")
        self.assertEqual(note["lexicon_license_note"], "lexicon test license")

    def test_existing_human_gloss_and_transliteration_are_not_overwritten(self):
        add_original_note(
            {
                "reference": "MAT 14:27",
                "language": "grc",
                "lemma": "θαρσέω",
                "transliteration": "human-translit",
                "gloss": "사람이 검토한 뜻",
                "source": "Reviewed notes",
                "license_note": "local",
            },
            self.db,
        )
        import_original_lexicon(
            [{"language": "grc", "lemma": "θαρσέω", "transliteration": "dictionary", "gloss": "사전 뜻"}],
            "Dictionary",
            "licensed",
            self.db,
        )
        note = original_notes("MAT 14:27", self.db)[0]
        self.assertEqual(note["gloss"], "사람이 검토한 뜻")
        self.assertEqual(note["transliteration"], "human-translit")
        self.assertFalse(note["lexicon_enriched"])

    def test_hebrew_strong_key_variants_match(self):
        self.assertEqual(lexicon_lookup_key("he", "H7225"), "7225")
        self.assertEqual(lexicon_lookup_key("he", "c/7225"), "7225")
        self.assertEqual(lexicon_lookup_key("he", "7225"), "7225")
        self.assertEqual(lexicon_lookup_key("he", "3588 a"), "3588")
        self.assertEqual(lexicon_lookup_key("he", "H3588a"), "3588")

    def test_import_is_idempotent_and_updates_same_source(self):
        item = [{"language": "grc", "lemma": "λόγος", "transliteration": "logos", "gloss": "말씀"}]
        first = import_original_lexicon(item, "Lexicon", "license", self.db)
        second = import_original_lexicon(item, "Lexicon", "license", self.db)
        changed = import_original_lexicon(
            [{"language": "grc", "lemma": "λόγος", "transliteration": "logos", "gloss": "말/말씀"}],
            "Lexicon",
            "license",
            self.db,
        )
        self.assertEqual(first["imported"], 1)
        self.assertEqual(second["unchanged"], 1)
        self.assertEqual(changed["updated"], 1)
        self.assertEqual(original_lexicon_stats(self.db)["total"], 1)


if __name__ == "__main__":
    unittest.main()
