import unittest

from fastapi import HTTPException

import app.main as main
from app.importers import convert_original_note_source
from app.main import OriginalNoteRequest
from app.references import primary_original_language, validate_primary_original_language


class V30OriginalLanguageGuidanceTests(unittest.TestCase):
    def test_testament_primary_language_is_derived_from_canonical_book(self):
        self.assertEqual(primary_original_language("Matt 14:27-31"), "grc")
        self.assertEqual(primary_original_language("Isaiah 41:10"), "he")

    def test_reference_info_normalizes_range_and_recommends_greek_for_matthew(self):
        info = main.reference_info("Matt 14:27-31")
        self.assertEqual(info["reference"], "MAT 14:27-31")
        self.assertEqual(info["first_reference"], "MAT 14:27")
        self.assertEqual(info["testament"], "NT")
        self.assertEqual(info["primary_original_language"], "grc")
        self.assertTrue(info["is_range"])

    def test_manual_matthew_hebrew_mismatch_is_rejected_before_save(self):
        request = OriginalNoteRequest(reference="MAT 14:27", language="he", lemma="θαρσέω")
        with self.assertRaises(HTTPException) as raised:
            main.create_original_note(request)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("헬라어", raised.exception.detail)

    def test_original_file_preview_rejects_cross_testament_language(self):
        source = "reference,language,lemma\nMAT 14:27,he,wrong\n"
        with self.assertRaisesRegex(ValueError, "언어가 성경 구분과 맞지"):
            convert_original_note_source(source, "csv")

    def test_non_hebrew_greek_language_code_is_not_falsely_rejected(self):
        self.assertEqual(validate_primary_original_language("DAN 2:4", "arc"), "he")


if __name__ == "__main__":
    unittest.main()
