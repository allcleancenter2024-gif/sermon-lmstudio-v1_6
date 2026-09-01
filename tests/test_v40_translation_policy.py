import unittest

from app.core import (
    build_sermon_prompt,
    build_translation_policy,
    canonical_english_translation,
    interpretation_stage_for_passage,
    sort_interpretation_passages,
    translation_policy_for_passage,
)


def passage(translation, language="en"):
    return {
        "translation": translation, "language": language, "reference": "JHN 3:16",
        "text": f"registered {translation} text", "license_note": "test license",
    }


class EnglishTranslationPolicyTests(unittest.TestCase):
    def test_three_groups_and_expression_only_guard(self):
        self.assertEqual(translation_policy_for_passage(passage("ESV"))["group"], "tier1")
        self.assertEqual(translation_policy_for_passage(passage("NRSVue"))["group"], "tier2")
        self.assertEqual(translation_policy_for_passage(passage("KJV"))["group"], "tier3")
        self.assertTrue(translation_policy_for_passage(passage("Amplified Bible (AMP)"))["expression_only"])
        self.assertTrue(translation_policy_for_passage(passage("The Message (MSG)"))["expression_only"])

    def test_gnt_english_translation_is_not_mistaken_for_greek_original(self):
        self.assertEqual(canonical_english_translation(passage("GNT", "en")), "GNT")
        self.assertNotEqual(interpretation_stage_for_passage(passage("GNT", "en")), "original_language")
        self.assertEqual(interpretation_stage_for_passage(passage("Greek New Testament", "grc")), "original_language")

    def test_full_priority_order_puts_core_before_extension_and_aids(self):
        names = ["The Message", "NLT", "KJV", "NRSVue", "NET", "CSB", "NIV", "NASB", "ESV", "개역개정"]
        rows = [passage(x, "ko" if x == "개역개정" else "en") for x in names]
        rows.append(passage("SBLGNT", "grc"))
        ordered = [x["translation"] for x in sort_interpretation_passages(rows)]
        self.assertEqual(ordered, ["개역개정", "SBLGNT", "ESV", "NASB", "NIV", "CSB", "NET", "NRSVue", "NLT", "KJV", "The Message"])

    def test_core_engine_requires_korean_original_and_all_tier1_texts(self):
        rows = [passage("개역개정", "ko"), passage("SBLGNT", "grc")]
        rows.extend(passage(x) for x in ("ESV", "NASB", "NIV", "CSB", "NET"))
        policy = build_translation_policy(rows)
        self.assertTrue(policy["core_engine_ready"])
        self.assertEqual(policy["missing_core"], [])

    def test_net_notes_alone_do_not_satisfy_net_core_text(self):
        rows = [passage("개역개정", "ko"), passage("SBLGNT", "grc"), passage("NET Notes")]
        rows.extend(passage(x) for x in ("ESV", "NASB", "NIV", "CSB"))
        policy = build_translation_policy(rows)
        self.assertFalse(policy["core_engine_ready"])
        self.assertIn("NET", policy["missing_core"])
        self.assertTrue(policy["net_notes_ready"])
        self.assertFalse(policy["net_translation_ready"])

    def test_prompt_forbids_amp_and_message_as_original_or_doctrinal_evidence(self):
        rows = [passage("개역개정", "ko"), passage("ESV"), passage("AMP"), passage("The Message")]
        system, user = build_sermon_prompt({"topic": "사랑", "main_reference": "JHN 3:16"}, rows)
        combined = system + user
        self.assertIn("AMP와 The Message는 표현 이해에만 사용", combined)
        self.assertIn("원어 의미·교리·번역 쟁점의 증거로 사용하지 않습니다", combined)
        self.assertLess(user.index("[ESV |"), user.index("[AMP |"))
        self.assertLess(user.index("[AMP |"), user.index("[The Message |"))


if __name__ == "__main__":
    unittest.main()
