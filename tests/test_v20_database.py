import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.core import (
    add_passage,
    bible_database_dashboard,
    bible_database_integrity,
    build_rag_index,
    delete_bible_translation,
    rag_stats,
    register_translation_license,
)
from app.importers import convert_bible_source
from app.main import remove_database_translation


class V20ConverterAndDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "bible.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_converter_supports_json_csv_tsv(self):
        cases = {
            "json": '[{"reference":"John 3:16","text":"For God so loved"}]',
            "csv": 'book,chapter,verse,text\nJohn,3,16,"For God, so loved"\n',
            "tsv": "reference\ttext\nJohn 3:16\tFor God so loved\n",
        }
        for fmt, source in cases.items():
            resolved, items = convert_bible_source(source, fmt)
            self.assertEqual(resolved, fmt)
            self.assertEqual(items[0]["reference"], "John 3:16")
            self.assertTrue(items[0]["text"])

    def test_converter_supports_usfm(self):
        source = "\\id JHN\n\\c 3\n\\v 16 For God so loved.\n\\v 17 For God sent his Son.\n"
        resolved, items = convert_bible_source(source, "auto")
        self.assertEqual(resolved, "usfm")
        self.assertEqual([item["reference"] for item in items], ["JHN 3:16", "JHN 3:17"])

    def test_converter_supports_osis_xml(self):
        source = '<osis><verse osisID="John.3.16">For God <hi>so</hi> loved</verse></osis>'
        resolved, items = convert_bible_source(source, "auto")
        self.assertEqual(resolved, "osis")
        self.assertEqual(items, [{"reference": "John 3:16", "text": "For God so loved"}])

    def test_converter_rejects_duplicate_references(self):
        source = '[{"reference":"John 3:16","text":"A"},{"reference":"john 3:16","text":"B"}]'
        with self.assertRaisesRegex(ValueError, "중복 성경 참조"):
            convert_bible_source(source, "json")

    def test_database_dashboard_and_delete_remove_only_target_vectors(self):
        add_passage("WEB", "en", "John 3:16", "WEB text", "Public Domain", self.db)
        add_passage("WLC", "he", "Gen 1:1", "Hebrew text", "Public Domain", self.db)

        class FakeEmbeddingClient:
            def embeddings(self, model, texts):
                return [[1.0, 0.0] for _ in texts]

        build_rag_index(FakeEmbeddingClient(), "fake-embed", self.db)
        dashboard = bible_database_dashboard(self.db)
        self.assertEqual(dashboard["database"]["passages"], 2)
        self.assertEqual({row["translation"] for row in dashboard["translations"]}, {"WEB", "WLC"})
        removed = delete_bible_translation("WEB", self.db)
        self.assertEqual(removed["deleted_passages"], 1)
        self.assertEqual(removed["deleted_vectors"], 1)
        self.assertEqual(bible_database_dashboard(self.db)["translations"][0]["translation"], "WLC")
        self.assertEqual(rag_stats(self.db)["indexed"], 1)

    def test_integrity_reports_fulltext_permission_conflict(self):
        add_passage("LICENSED", "ko", "테스트 1:1", "허가 테스트", "허가됨", self.db)
        register_translation_license({
            "translation": "LICENSED", "license_status": "restricted", "allow_fulltext": False,
            "copyright_holder": "holder", "permission_ref": "", "source_url": "", "notes": "",
        }, self.db)
        report = bible_database_integrity(self.db)
        self.assertFalse(report["ok"])
        self.assertEqual(report["blocked_fulltext"], 1)
        self.assertIn("전문 저장", report["issues"][0])

    def test_delete_api_requires_exact_confirmation_value(self):
        with patch("app.main.delete_bible_translation") as deleter:
            with self.assertRaises(HTTPException) as raised:
                remove_database_translation("WEB", confirm="WRONG")
            self.assertEqual(raised.exception.status_code, 400)
            deleter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
