import tempfile
import unittest
from pathlib import Path

from app import main
from app.version import APP_VERSION
from app.core import (
    add_original_note, db_stats, import_original_lexicon, import_original_notes,
    original_language_coverage, original_notes,
)
from app.importers import classify_original_language_source, convert_lexicon_source


class V40OriginalCoverageTests(unittest.TestCase):
    def test_current_runtime_and_workflow_version(self):
        self.assertEqual(main.APP_VERSION, APP_VERSION)
        self.assertEqual(main.workflow_config()["version"], 40)

    def test_coverage_reports_missing_verse_in_range(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "bible.db"
            import_original_notes(
                [{"reference": "GEN 1:1", "language": "he", "lemma": "7225", "morphology": "HNcfsa"}],
                "OSHB test", "CC BY 4.0", db,
            )
            result = original_language_coverage("Genesis 1:1-2", db)
            self.assertFalse(result["ready"])
            self.assertEqual(result["coverage_percent"], 50)
            self.assertEqual(result["missing_references"], ["GEN 1:2"])

    def test_coverage_counts_lexicon_enrichment_without_changing_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "bible.db"
            import_original_notes(
                [{"reference": "GEN 1:1", "language": "he", "lemma": "H7225", "morphology": "HNcfsa"}],
                "OSHB test", "CC BY 4.0", db,
            )
            import_original_lexicon(
                [{"language": "he", "lemma": "7225", "gloss": "beginning", "transliteration": "reshith"}],
                "licensed lexicon", "test license", db,
            )
            result = original_language_coverage("GEN 1:1", db)
            self.assertTrue(result["ready"])
            self.assertEqual(result["glossed_count"], 1)
            self.assertEqual(result["transliterated_count"], 1)
            self.assertEqual(result["sources"], ["OSHB test"])
            self.assertEqual(db_stats(db)["original_lexicon"], 1)

    def test_ui_allows_wrong_role_files_to_reach_router(self):
        html = Path("templates/index.html").read_text(encoding="utf-8")
        self.assertIn('id="checkOriginalCoverage"', html)
        self.assertIn('id="originalCoverageStatus"', html)
        lexicon_input = html.split('id="lexiconImportFile"', 1)[1].split(">", 1)[0]
        for extension in (".zip", ".xml", ".txt", ".json", ".csv", ".tsv"):
            self.assertIn(extension, lexicon_input)
        self.assertIn("압축을 풀지 않은 채", html)

    def test_strongs_greek_xml_is_a_lexicon_and_enriches_morphgnt_unicode_variant(self):
        xml = """<?xml version='1.0'?><strongsdictionary><entries>
        <entry strongs='00931'><greek unicode='βίβλος' translit='bíblos'/>
        <strongs_def>book, scroll</strongs_def><kjv_def>book</kjv_def></entry>
        </entries></strongsdictionary>"""
        self.assertEqual(classify_original_language_source(xml), "strongs_greek_lexicon")
        resolved, items = convert_lexicon_source(xml, "auto")
        self.assertEqual(resolved, "strongs_greek_xml")
        self.assertEqual(items[0]["language"], "grc")
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "bible.db"
            add_original_note({
                "reference": "MAT 1:1", "language": "grc", "lemma": "βίβλος",
                "morphology": "N- ----NSF-", "source": "MorphGNT", "license_note": "test",
            }, db)
            import_original_lexicon(items, "Strong Greek XML", "CC0 test", db)
            note = original_notes("MAT 1:1", db)[0]
            self.assertEqual(note["gloss"], "book, scroll")
            self.assertEqual(note["transliteration"], "bíblos")

    def test_hebrew_strongs_xml_uses_strong_id_as_oshb_join_key(self):
        xml = """<?xml version='1.0'?><lexicon xmlns='http://openscriptures.github.com/morphhb/namespace'>
        <entry id='H7225'><w xlit='rēʾšît' xml:lang='heb'>רֵאשִׁית</w>
        <meaning><def>beginning</def>, first</meaning><usage>beginning</usage></entry>
        </lexicon>"""
        self.assertEqual(classify_original_language_source(xml), "hebrew_strongs_lexicon")
        resolved, items = convert_lexicon_source(xml, "xml")
        self.assertEqual(resolved, "hebrew_strongs_xml")
        self.assertEqual(items[0]["lemma"], "H7225")
        self.assertEqual(items[0]["gloss"], "beginning, first")

    def test_strongs_lexicon_merges_repeated_lemma_senses(self):
        xml = """<strongsdictionary><entry><greek unicode=\"λόγος\" translit=\"logos\"/><strongs_def>word</strongs_def></entry><entry><greek unicode=\"λόγος\" translit=\"logos\"/><strongs_def>message</strongs_def></entry></strongsdictionary>"""
        source_format, items = convert_lexicon_source(xml, "strongs_greek_xml")
        self.assertEqual(source_format, "strongs_greek_xml")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["gloss"], "word · message")

    def test_ui_preserves_routed_original_role_on_second_preview_click(self):
        js = Path("static/app.js").read_text(encoding="utf-8")
        self.assertIn("routedOriginalFile&&file===routedOriginalFile", js)
        self.assertIn("분류된 원어 근거 다시 검사", js)
        self.assertIn("strongs_greek_xml", Path("templates/index.html").read_text(encoding="utf-8"))

    def test_strongs_filename_hint_prevents_hebrew_dictionary_from_becoming_oshb_original(self):
        xml = "<lexicon><entry id='H1'><w>אב</w><meaning>father</meaning></entry></lexicon>"
        self.assertEqual(
            classify_original_language_source(xml, "HebrewStrong.xml"),
            "hebrew_strongs_lexicon",
        )

    def test_explicit_strongs_formats_are_accepted_by_api_request_schema(self):
        from app.main import LexiconConvertRequest
        self.assertEqual(
            LexiconConvertRequest(source_format="hebrew_strongs_xml", content="<x/>").source_format,
            "hebrew_strongs_xml",
        )
        self.assertEqual(
            LexiconConvertRequest(source_format="strongs_greek_xml", content="<x/>").source_format,
            "strongs_greek_xml",
        )

    def test_smart_original_wizard_is_primary_and_advanced_tools_are_collapsed(self):
        html = Path("templates/index.html").read_text(encoding="utf-8")
        js = Path("static/app.js").read_text(encoding="utf-8")
        for element_id in (
            "smartOriginalFile", "previewSmartOriginal", "smartRoleCard",
            "smartOriginalSource", "smartOriginalLicense", "runSmartOriginal",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("고급 기능: 파일 형식과 등록 위치를 직접 지정하기", html)
        self.assertIn("filename:file.name", js)
        self.assertIn("previewSmartOriginal", js)
        self.assertIn("bible_passages", js)
        self.assertIn("pendingSmartBibleImport", js)
        self.assertIn("1Cor.xml", html)
        self.assertIn("lemma·형태 정보까지 필요하면", html)


if __name__ == "__main__":
    unittest.main()
