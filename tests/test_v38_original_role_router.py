import unittest

from app.importers import classify_original_language_source, convert_lexicon_source
from app.main import OriginalLanguageClassifyRequest, classify_original_language_file


MORPHGNT_SAMPLE = "610101 N- ----NSM- βιβλος βιβλος βιβλος βίβλος\n"
OSHB_SAMPLE = "<osis><osisText><verse osisID='Gen.1.1'><w lemma='7225' morph='HNcfsa'>x</w></verse></osisText></osis>"
LEXICON_TSV = "language\tlemma\tgloss\ngrс\tλόγος\tword\n"
SBLGNT_1COR_XML = """<book id='1Co'><p><verse-number id='1 Corinthians 1:1'>1:1</verse-number><w>Παῦλος</w></p></book>"""


class V38OriginalRoleRouterTests(unittest.TestCase):
    def test_morphgnt_is_classified_as_original_evidence(self):
        self.assertEqual(classify_original_language_source(MORPHGNT_SAMPLE), "morphgnt_original")

    def test_morphgnt_is_rejected_from_lexicon_even_when_user_selected_tsv(self):
        with self.assertRaisesRegex(ValueError, "MorphGNT"):
            convert_lexicon_source(MORPHGNT_SAMPLE, "tsv")

    def test_oshb_is_classified_as_original_evidence(self):
        self.assertEqual(classify_original_language_source(OSHB_SAMPLE), "oshb_original")

    def test_lexicon_header_is_classified_as_lexicon(self):
        self.assertEqual(classify_original_language_source(LEXICON_TSV), "lexicon")

    def test_classify_api_returns_original_notes_target_for_morphgnt(self):
        result = classify_original_language_file(OriginalLanguageClassifyRequest(content=MORPHGNT_SAMPLE))
        self.assertEqual(result["target"], "original_notes")
        self.assertEqual(result["format"], "morphgnt")

    def test_sblgnt_book_xml_routes_to_bible_passages(self):
        self.assertEqual(classify_original_language_source(SBLGNT_1COR_XML, "1Cor.xml"), "sblgnt_bible")
        result = classify_original_language_file(
            OriginalLanguageClassifyRequest(content=SBLGNT_1COR_XML, filename="1Cor.xml")
        )
        self.assertEqual(result["target"], "bible_passages")
        self.assertEqual(result["format"], "sblgnt_xml")
        self.assertIn("SBLGNT", result["label"])


if __name__ == "__main__":
    unittest.main()
