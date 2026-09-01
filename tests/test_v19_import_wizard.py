import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import BibleWizardImportRequest, bible_import_presets, wizard_bible_import


class V19ImportWizardTests(unittest.TestCase):
    def _request(self, **changes):
        data = {
            "preset_id": "web",
            "translation": "MALICIOUS-OVERRIDE",
            "language": "xx",
            "license_note": "wrong",
            "source_url": "https://wrong.invalid",
            "confirmed": True,
            "items": [{"reference": "John 3:16", "text": "Test verse text"}],
        }
        data.update(changes)
        return BibleWizardImportRequest(**data)

    def test_public_presets_are_explicit_and_do_not_include_restricted_korean_text(self):
        result = bible_import_presets()
        ids = {item["id"] for item in result["items"]}
        self.assertTrue({"web", "wlc", "sblgnt", "licensed_custom"}.issubset(ids))
        self.assertNotIn("개역개정", {item["translation"] for item in result["items"]})
        self.assertEqual(result["format"]["max_items_per_request"], 5000)

    def test_public_preset_metadata_cannot_be_overridden_by_browser_payload(self):
        captured = []

        def fake_import(items):
            captured.extend(items)
            return len(items)

        with (
            patch("app.main.import_items", side_effect=fake_import),
            patch("app.main.db_stats", return_value={"passages": 1, "translations": 1, "languages": 1}),
        ):
            result = wizard_bible_import(self._request())
        self.assertEqual(result["translation"], "WEB")
        self.assertEqual(captured[0]["translation"], "WEB")
        self.assertEqual(captured[0]["language"], "en")
        self.assertIn("Public Domain", captured[0]["license_note"])
        self.assertIn("ebible.org", captured[0]["license_note"])

    def test_custom_licensed_import_requires_fulltext_permission_registry(self):
        request = self._request(
            preset_id="licensed_custom",
            translation="개역개정-정식허가본",
            language="ko",
            license_note="정식 사용 허가 번호 TEST-001",
            source_url="https://license.example.test",
        )
        with (
            patch("app.main.translation_licenses", return_value=[]),
            patch("app.main.import_items") as importer,
        ):
            with self.assertRaises(HTTPException) as raised:
                wizard_bible_import(request)
            self.assertEqual(raised.exception.status_code, 403)
            importer.assert_not_called()

    def test_custom_licensed_import_succeeds_after_fulltext_permission(self):
        request = self._request(
            preset_id="licensed_custom",
            translation="한국어-정식허가본",
            language="ko",
            license_note="정식 사용 허가 번호 TEST-002",
            source_url="https://license.example.test/source",
        )
        captured = []
        with (
            patch("app.main.translation_licenses", return_value=[{
                "translation": "한국어-정식허가본", "allow_fulltext": 1,
            }]),
            patch("app.main.import_items", side_effect=lambda items: captured.extend(items) or len(items)),
            patch("app.main.db_stats", return_value={"passages": 1, "translations": 1, "languages": 1}),
        ):
            result = wizard_bible_import(request)
        self.assertEqual(result["imported"], 1)
        self.assertEqual(captured[0]["translation"], "한국어-정식허가본")
        self.assertIn("TEST-002", captured[0]["license_note"])
        self.assertIn("license.example.test/source", captured[0]["license_note"])

    def test_import_requires_explicit_license_confirmation(self):
        with patch("app.main.import_items") as importer:
            with self.assertRaises(HTTPException) as raised:
                wizard_bible_import(self._request(confirmed=False))
            self.assertEqual(raised.exception.status_code, 400)
            importer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
