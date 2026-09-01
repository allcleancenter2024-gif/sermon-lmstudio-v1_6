import unittest

from app.core import (
    analyze_social_neutrality,
    build_post_generation_quality,
    build_sermon_prompt,
    build_social_context_policy,
)


PASSAGES = [{
    "translation": "개역개정", "language": "ko", "reference": "MIC 6:8",
    "text": "정의를 행하며 인자를 사랑하며", "license_note": "test license",
}]


class SocialNeutralityTests(unittest.TestCase):
    def test_policy_activates_for_social_and_world_affairs_context(self):
        policy = build_social_context_policy("불안한 시대의 믿음", "2026년 사회 갈등과 경제 양극화, 국제 전쟁")
        self.assertTrue(policy["active"])
        self.assertEqual([x["key"] for x in policy["biblical_lenses"]],
                         ["justice", "love", "reconciliation", "responsibility"])

    def test_prompt_uses_translation_tips_without_treating_esv_as_original_proof(self):
        rows = PASSAGES + [
            {"translation": "ESV", "language": "en", "reference": "MIC 6:8", "text": "do justice", "license_note": "test"},
            {"translation": "NIV", "language": "en", "reference": "MIC 6:8", "text": "act justly", "license_note": "test"},
            {"translation": "NLT", "language": "en", "reference": "MIC 6:8", "text": "do what is right", "license_note": "test"},
            {"translation": "The Message", "language": "en", "reference": "MIC 6:8", "text": "fair and just", "license_note": "test"},
        ]
        system, user = build_sermon_prompt({
            "topic": "공의와 평화", "details": "2026년 사회 갈등과 국제 불안", "main_reference": "MIC 6:8",
        }, rows)
        combined = system + user
        self.assertIn("ESV/NASB는 원문 구조와 핵심어를 발견하는 단서", combined)
        self.assertIn("원래 의미는 등록된 히브리어/헬라어로 확인", combined)
        self.assertIn("NIV/NLT는 현대적인 문장과 적용", combined)
        self.assertIn("The Message는 생동감 있는 표현 아이디어", combined)
        self.assertIn("공의 Justice", user)
        self.assertIn("특정 정당·정치인·이념을 지지하거나 공격하지 않습니다", user)
        self.assertIn("국제 사건을 하나님의 숨은 뜻·심판·예언 성취로 확정하지 않습니다", user)

    def test_audit_flags_partisan_direction_and_geopolitical_divine_certainty(self):
        sermon = "이번 선거에서는 특정 후보를 지지해야 합니다. 이 전쟁은 하나님의 심판이며 예언의 성취입니다."
        result = analyze_social_neutrality(sermon)
        self.assertEqual(result["issue_count"], 2)
        quality = build_post_generation_quality(
            sermon=sermon, passages=PASSAGES, word_notes=[], doctrine_notes=[], target_minutes=15, actual_minutes=15,
        )
        self.assertEqual(next(x for x in quality["checks"] if x["key"] == "social_neutrality")["issue_count"], 2)

    def test_neutral_biblical_application_and_explicit_guard_are_not_flagged(self):
        sermon = "특정 정당을 지지해서는 안 됩니다. 사회 갈등 속에서 공의와 사랑, 화해와 책임을 실천합시다."
        self.assertEqual(analyze_social_neutrality(sermon)["issue_count"], 0)


if __name__ == "__main__":
    unittest.main()
