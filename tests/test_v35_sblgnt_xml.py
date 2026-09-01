import unittest

from app.importers import convert_bible_source, detect_source_format
from app.main import BibleConvertRequest


SBLGNT_MATTHEW_SAMPLE = """\
<book id="Mt">
  <title>ΚΑΤΑ ΜΑΘΘΑΙΟΝ</title>
  <p>
    <verse-number id="Matthew 14:27">14:27</verse-number>
    <w>εὐθὺς</w><suffix></suffix>
    <w>δὲ</w><suffix></suffix>
    <w>ἐλάλησεν</w><suffix>, </suffix>
    <w>λέγων</w><suffix>· </suffix>
    <w>θαρσεῖτε</w><suffix>· </suffix>
  </p>
  <p>
    <verse-number id="Matthew 14:28">28</verse-number>
    <w>ἀποκριθεὶς</w><suffix></suffix>
    <w>δὲ</w><suffix></suffix>
    <w>αὐτῷ</w><suffix>· </suffix>
  </p>
</book>
"""

SBLGNT_FIRST_CORINTHIANS_SAMPLE = """\
<book id="1Co">
  <title>ΠΡΟΣ ΚΟΡΙΝΘΙΟΥΣ Α</title>
  <p>
    <verse-number id="1 Corinthians 1:1">1:1</verse-number>
    <w>Παῦλος</w><suffix>, </suffix><w>κλητὸς</w><suffix> </suffix><w>ἀπόστολος</w>
  </p>
</book>
"""


class V35SblgntXmlTests(unittest.TestCase):
    def test_native_sblgnt_xml_is_auto_detected_and_normalized(self):
        self.assertEqual(detect_source_format(SBLGNT_MATTHEW_SAMPLE), "sblgnt_xml")
        resolved, items = convert_bible_source(SBLGNT_MATTHEW_SAMPLE, "auto")
        self.assertEqual(resolved, "sblgnt_xml")
        self.assertEqual([item["reference"] for item in items], ["MAT 14:27", "MAT 14:28"])
        self.assertIn("θαρσεῖτε", items[0]["text"])

    def test_osis_selection_is_safely_reclassified_for_official_sblgnt_xml(self):
        resolved, items = convert_bible_source(SBLGNT_MATTHEW_SAMPLE, "osis")
        self.assertEqual(resolved, "sblgnt_xml")
        self.assertEqual(len(items), 2)

    def test_first_corinthians_book_xml_is_normalized(self):
        resolved, items = convert_bible_source(SBLGNT_FIRST_CORINTHIANS_SAMPLE, "auto")
        self.assertEqual(resolved, "sblgnt_xml")
        self.assertEqual(items[0]["reference"], "1CO 1:1")
        self.assertIn("Παῦλος", items[0]["text"])

    def test_lexical_index_like_xml_gets_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "어휘/색인"):
            convert_bible_source("<LexicalIndex><Lexeme lemma='λόγος'/></LexicalIndex>", "osis")

    def test_api_schema_accepts_explicit_sblgnt_xml_format(self):
        request = BibleConvertRequest(source_format="sblgnt_xml", content=SBLGNT_MATTHEW_SAMPLE)
        self.assertEqual(request.source_format, "sblgnt_xml")


if __name__ == "__main__":
    unittest.main()
