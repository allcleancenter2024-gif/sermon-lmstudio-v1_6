from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core import add_original_note, add_passage, build_research_packet, build_sermon_prompt


class V25EvidenceGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "bible.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_range_requires_one_continuous_translation_not_mixed_coverage(self):
        add_passage("WEB", "en", "MAT 14:27", "v27", "Public Domain", self.db)
        add_passage("WEB", "en", "MAT 14:29", "v29", "Public Domain", self.db)
        add_passage("ALT", "en", "MAT 14:28", "v28", "licensed", self.db)
        add_passage("ALT", "en", "MAT 14:30", "v30", "licensed", self.db)
        packet = build_research_packet("MAT 14:27-30", db_path=self.db)
        self.assertEqual(packet["missing_main_references"], [])
        self.assertEqual(packet["complete_translations"], [])
        self.assertFalse(packet["readiness"]["continuous_translation_ready"])
        self.assertFalse(packet["readiness"]["generation_ready"])

    def test_translation_matrix_preserves_per_verse_parallel_texts(self):
        for translation in ("WEB", "ALT"):
            for verse in (27, 28):
                add_passage(translation, "en", f"MAT 14:{verse}", f"{translation} verse {verse}", "ok", self.db)
        packet = build_research_packet("MAT 14:27-28", db_path=self.db)
        self.assertEqual(packet["complete_translations"], ["ALT", "WEB"])
        self.assertEqual(len(packet["translation_matrix"]), 2)
        self.assertEqual({x["translation"] for x in packet["translation_matrix"][0]["variants"]}, {"WEB", "ALT"})

    def test_original_note_missing_provenance_is_flagged(self):
        add_passage("WEB", "en", "MAT 14:27", "v27", "Public Domain", self.db)
        add_original_note({"reference": "MAT 14:27", "language": "grc", "lemma": "θαρσέω", "gloss": "담대하다"}, self.db)
        packet = build_research_packet("MAT 14:27", db_path=self.db)
        self.assertEqual(len(packet["original_risk_flags"]), 1)
        self.assertIn("출처", packet["original_risk_flags"][0]["reason"])
        self.assertIn("사용조건", packet["original_risk_flags"][0]["reason"])

    def test_doctrine_alignment_rejects_wrong_tradition(self):
        add_passage("WEB", "en", "MAT 14:27", "v27", "Public Domain", self.db)
        doctrine = [{"tradition": "침례교", "title": "문서", "section": "1", "text": "내용"}]
        packet = build_research_packet("MAT 14:27", doctrine_notes=doctrine, db_path=self.db, tradition="장로교")
        self.assertFalse(packet["readiness"]["doctrine_ready"])
        self.assertEqual(packet["doctrine_alignment"]["conflicts"], ["침례교"])

    def test_prompt_keeps_original_reference_and_license_provenance(self):
        passages = [{"translation": "WEB", "language": "en", "reference": "MAT 14:27", "text": "text", "license_note": "PD"}]
        notes = [{"reference": "MAT 14:27", "language": "grc", "lemma": "θαρσέω", "transliteration": "tharseo", "gloss": "담대하다", "morphology": "verb", "source": "source", "license_note": "license"}]
        _, prompt = build_sermon_prompt({"topic": "믿음", "minutes": 15}, passages, notes, [])
        self.assertIn("[MAT 14:27 | grc]", prompt)
        self.assertIn("사용조건: license", prompt)
        self.assertIn("목표 낭독시간: 약 15분", prompt)


if __name__ == "__main__":
    unittest.main()
