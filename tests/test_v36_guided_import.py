import unittest
from pathlib import Path

from app import main


ROOT = Path(__file__).resolve().parents[1]


class V36GuidedImportTests(unittest.TestCase):
    def test_runtime_version_is_v36(self):
        config = main.workflow_config()
        self.assertEqual(config["version"], 40)
        self.assertEqual(config["app_version"], "40.9.10")

    def test_beginner_import_help_exists(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="bibleSimpleGuide"', html)
        self.assertIn('id="bibleFormatHelp"', html)
        self.assertIn("프로그램이 자동 판별", html)

    def test_public_preset_uses_auto_detection_and_lexical_index_is_blocked_early(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("format.value='auto';format.disabled=!custom", js)
        self.assertIn("name==='lexicalindex.xml'", js)
        self.assertIn("Matt.xml", js)
        self.assertIn("sblgnt.xml", js)


if __name__ == "__main__":
    unittest.main()
