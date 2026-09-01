from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.core import add_original_note, add_passage, build_research_packet
from app.main import SermonRequest, generate_sermon


class V24ResearchPacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "bible.db"
        for verse in range(27, 32):
            add_passage("WEB", "en", f"MAT 14:{verse}", f"Matthew verse {verse}", "Public Domain", self.db)
        add_original_note(
            {"reference": "MAT 14:27", "language": "grc", "lemma": "θαρσέω", "gloss": "담대하다"},
            self.db,
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_main_passage_is_merged_before_search_results(self):
        search = [{
            "translation": "WEB", "language": "en", "reference": "JHN 14:1",
            "text": "Related search result", "license_note": "Public Domain",
        }]
        doctrine = [{"tradition": "공통", "title": "교리", "section": "1", "text": "교리 근거"}]
        packet = build_research_packet("MATT 14:27~31", search, doctrine, self.db)
        refs = [x["reference"] for x in packet["bible_sources"]]
        self.assertEqual(refs[:5], [f"MAT 14:{verse}" for verse in range(27, 32)])
        self.assertEqual(refs[-1], "JHN 14:1")
        self.assertTrue(packet["readiness"]["generation_ready"])
        self.assertTrue(packet["readiness"]["original_language_ready"])
        self.assertTrue(packet["readiness"]["doctrine_ready"])

    def test_missing_verse_marks_range_not_ready(self):
        # Only four of the requested five verses are copied into a second DB.
        partial = Path(self.tmp.name) / "partial.db"
        for verse in range(27, 31):
            add_passage("WEB", "en", f"MAT 14:{verse}", f"Matthew verse {verse}", "Public Domain", partial)
        packet = build_research_packet("MAT 14:27-31", db_path=partial)
        self.assertFalse(packet["readiness"]["generation_ready"])
        self.assertEqual(packet["missing_main_references"], ["MAT 14:31"])

    def test_generation_blocks_incomplete_main_range_before_chat(self):
        incomplete = {
            "readiness": {"generation_ready": False},
            "missing_main_references": ["MAT 14:31"],
        }
        with (
            patch("app.main.db_stats", return_value={"passages": 4}),
            patch("app.main._collect_research_packet", return_value=incomplete),
            patch("app.main.LMStudioClient") as client_cls,
        ):
            with self.assertRaises(HTTPException) as raised:
                generate_sermon(SermonRequest(topic="믿음", main_reference="MAT 14:27-31"))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("MAT 14:31", raised.exception.detail)
        client_cls.return_value.chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
