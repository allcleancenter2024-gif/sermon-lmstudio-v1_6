import unittest

from app.importers import convert_original_note_source
from app.main import OriginalNoteConvertRequest


class V31NativeOriginalImportTests(unittest.TestCase):
    def test_morphgnt_native_text_auto_detects_and_maps_matthew(self):
        source = (
            "010101 N- ----NSF- Βίβλος Βίβλος βίβλος βίβλος\n"
            "011427 V- 2PAI-S-- θαρσεῖτε θαρσεῖτε θαρσεῖτε θαρσέω\n"
        )
        resolved, items = convert_original_note_source(source, "auto")
        self.assertEqual(resolved, "morphgnt")
        self.assertEqual(items[1]["reference"], "MAT 14:27")
        self.assertEqual(items[1]["language"], "grc")
        self.assertEqual(items[1]["lemma"], "θαρσέω")
        self.assertEqual(items[1]["morphology"], "V- 2PAI-S--")

    def test_morphgnt_repeated_same_lemma_and_morphology_in_verse_is_collapsed(self):
        source = (
            "010101 N- ----NSF- Βίβλος Βίβλος βίβλος βίβλος\n"
            "010101 N- ----NSF- Βίβλος Βίβλος βίβλος βίβλος\n"
        )
        _, items = convert_original_note_source(source, "morphgnt")
        self.assertEqual(len(items), 1)

    def test_oshb_osis_auto_detects_hebrew_and_aramaic(self):
        source = '''<?xml version="1.0" encoding="UTF-8"?>
        <osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace">
          <verse osisID="Gen.1.1"><w lemma="7225" morph="HNcfsa">בְּרֵאשִׁית</w></verse>
          <verse osisID="Dan.2.4"><w lemma="4430" morph="ANcmsa">מַלְכָּא</w></verse>
        </osis>'''
        resolved, items = convert_original_note_source(source, "auto")
        self.assertEqual(resolved, "oshb_osis")
        self.assertEqual(items[0]["reference"], "GEN 1:1")
        self.assertEqual(items[0]["language"], "he")
        self.assertEqual(items[1]["reference"], "DAN 2:4")
        self.assertEqual(items[1]["language"], "arc")

    def test_api_request_schema_accepts_native_formats(self):
        self.assertEqual(OriginalNoteConvertRequest(source_format="morphgnt", content="x").source_format, "morphgnt")
        self.assertEqual(OriginalNoteConvertRequest(source_format="oshb_osis", content="x").source_format, "oshb_osis")


if __name__ == "__main__":
    unittest.main()
