import tempfile
import unittest
from pathlib import Path

from app.core import (
    add_original_note,
    add_passage,
    build_interpretation_flow,
    build_research_packet,
    build_sermon_prompt,
    interpretation_stage_for_passage,
    sort_interpretation_passages,
)


def passage(translation, language="en"):
    return {
        "translation": translation,
        "language": language,
        "reference": "JHN 3:16",
        "text": f"{translation} registered text",
        "license_note": "test license",
    }


class InterpretationFlowTests(unittest.TestCase):
    def test_aliases_are_classified_without_matching_verse_text(self):
        self.assertEqual(interpretation_stage_for_passage(passage("개역개정-정식허가본", "ko")), "korean_base")
        self.assertEqual(interpretation_stage_for_passage(passage("NASB 2020")), "formal_equivalence")
        self.assertEqual(interpretation_stage_for_passage(passage("CSB")), "meaning_equivalence")
        self.assertEqual(interpretation_stage_for_passage(passage("NET Bible Notes")), "translation_notes")
        self.assertEqual(interpretation_stage_for_passage(passage("NET Bible")), "translation_notes")
        self.assertEqual(interpretation_stage_for_passage(passage("NLT")), "easy_expression")

    def test_registered_evidence_is_sorted_in_requested_exegesis_order(self):
        rows = [passage("NLT"), passage("NIV"), passage("ESV"), passage("개역개정", "ko"), passage("SBLGNT", "grc"), passage("NET Notes")]
        ordered = [x["translation"] for x in sort_interpretation_passages(rows)]
        self.assertEqual(ordered, ["개역개정", "SBLGNT", "ESV", "NIV", "NET Notes", "NLT"])

    def test_prompt_requires_synthesis_and_forbids_fabricating_missing_stages(self):
        rows = [passage("NLT"), passage("개역개정", "ko"), passage("ESV")]
        _, prompt = build_sermon_prompt({"topic": "하나님의 사랑", "main_reference": "JHN 3:16", "minutes": 15}, rows)
        self.assertLess(prompt.index("[개역개정 |"), prompt.index("[ESV |"))
        self.assertLess(prompt.index("[ESV |"), prompt.index("[NLT |"))
        self.assertIn("번역본을 나열하지 말고", prompt)
        self.assertIn("없는 번역이나 주석의 내용을 만들어내지 마십시오", prompt)
        self.assertIn("5. NET 번역·번역주석: 자료 없음 · 추측 금지", prompt)

    def test_research_packet_exposes_eight_stage_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "flow.db"
            add_passage("개역개정", "ko", "JHN 3:16", "개역개정 registered text", "test license", db)
            add_passage("ESV", "en", "JHN 3:16", "ESV registered text", "test license", db)
            add_original_note({
                "reference": "JHN 3:16", "language": "grc", "lemma": "ἀγαπάω",
                "transliteration": "agapao", "gloss": "love", "morphology": "verb",
                "source": "test source", "license_note": "test license",
            }, db)
            packet = build_research_packet("JHN 3:16", db_path=db)
        flow = packet["interpretation_flow"]
        self.assertEqual(len(flow), 8)
        by_key = {x["key"]: x for x in flow}
        self.assertTrue(by_key["korean_base"]["ready"])
        self.assertTrue(by_key["original_language"]["ready"])
        self.assertTrue(by_key["formal_equivalence"]["ready"])
        self.assertFalse(by_key["translation_notes"]["ready"])
        self.assertTrue(by_key["sermon"]["ready"])
        self.assertTrue(any("권장 해석 흐름 중 미등록 자료" in x for x in packet["warnings"]))

    def test_flow_marks_doctrine_ready_only_with_registered_evidence(self):
        flow = build_interpretation_flow([passage("개역개정", "ko")], [], [])
        self.assertFalse(next(x for x in flow if x["key"] == "doctrine")["ready"])
        doctrine = [{"tradition": "장로교", "title": "신앙고백", "text": "근거"}]
        flow = build_interpretation_flow([passage("개역개정", "ko")], [], doctrine)
        self.assertTrue(next(x for x in flow if x["key"] == "doctrine")["ready"])

    def test_net_notes_cannot_replace_a_complete_bible_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "notes-only.db"
            add_passage("NET Notes", "en", "JHN 3:16", "Registered translation note", "test license", db)
            packet = build_research_packet("JHN 3:16", db_path=db)
        self.assertFalse(packet["readiness"]["generation_ready"])
        self.assertEqual(packet["complete_translations"], [])
        self.assertTrue(next(x for x in packet["interpretation_flow"] if x["key"] == "translation_notes")["ready"])

    def test_net_bible_text_remains_a_complete_translation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "net-text.db"
            add_passage("NET Bible", "en", "JHN 3:16", "Registered NET verse", "test license", db)
            packet = build_research_packet("JHN 3:16", db_path=db)
        self.assertTrue(packet["readiness"]["generation_ready"])
        self.assertEqual(packet["complete_translations"], ["NET Bible"])
        self.assertTrue(packet["translation_policy"]["net_translation_ready"])


if __name__ == "__main__":
    unittest.main()
