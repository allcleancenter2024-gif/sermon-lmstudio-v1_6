import tempfile
import unittest
from pathlib import Path

from app.core import build_post_generation_quality, create_generation_audit, get_generation_audit


PASSAGES = [
    {"translation": "WEB", "language": "en", "reference": "John 3:16", "text": "For God so loved the world",
     "license_note": "Public Domain"},
]


class V27PostGenerationQualityTests(unittest.TestCase):
    def test_clean_15_minute_quality_passes(self):
        result = build_post_generation_quality(
            sermon="John 3:16 For God so loved the world.", passages=PASSAGES, word_notes=[], doctrine_notes=[],
            target_minutes=15, actual_minutes=15.0,
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["issue_count"], 0)
        self.assertEqual([c["key"] for c in result["checks"]],
                         ["scripture", "original", "doctrine", "translation", "social_neutrality", "duration"])

    def test_duration_deviation_is_review_issue(self):
        result = build_post_generation_quality(
            sermon="John 3:16 본문을 살펴봅니다.", passages=PASSAGES, word_notes=[], doctrine_notes=[],
            target_minutes=15, actual_minutes=18.0,
        )
        self.assertTrue(any(i["type"] == "duration" for i in result["issues"]))

    def test_direct_quote_mismatch_is_flagged(self):
        result = build_post_generation_quality(
            sermon='John 3:16 "This sentence is not in the registered translation."', passages=PASSAGES,
            word_notes=[], doctrine_notes=[], target_minutes=15, actual_minutes=15.0,
        )
        self.assertTrue(any(i["type"] == "translation" for i in result["issues"]))

    def test_original_and_doctrine_claims_without_registered_evidence_are_flagged(self):
        result = build_post_generation_quality(
            sermon="히브리어 원어가 이것을 뜻합니다. 이 교리는 신앙고백에 나옵니다.", passages=PASSAGES,
            word_notes=[], doctrine_notes=[], target_minutes=15, actual_minutes=15.0,
        )
        kinds = {i["type"] for i in result["issues"]}
        self.assertIn("original", kinds)
        self.assertIn("doctrine", kinds)

    def test_audit_stores_one_integrated_warning_per_failed_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "quality.db"
            quality = build_post_generation_quality(
                sermon="히브리어 원어를 설명합니다.", passages=PASSAGES, word_notes=[], doctrine_notes=[],
                target_minutes=15, actual_minutes=18.0,
            )
            audit = create_generation_audit(
                model="local", embedding_model="", search_mode="test", target_minutes=15, actual_minutes=18.0,
                passages=PASSAGES, unchecked=[], word_notes=[], doctrine_notes=[],
                citation_analysis=quality["citation_analysis"], post_generation_quality=quality, db_path=db,
            )
            self.assertEqual(audit["status"], "needs_review")
            self.assertEqual(len(audit["warnings"]), len({*audit["warnings"]}))
            loaded = get_generation_audit(audit["id"], db)
            self.assertEqual(loaded["post_generation_quality"]["method"], "post-generation-quality-v2")


if __name__ == "__main__":
    unittest.main()
