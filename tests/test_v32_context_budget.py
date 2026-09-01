import io
import unittest
import urllib.error
from unittest.mock import patch

from app.core import LMStudioClient, build_outline_prompt, build_sermon_prompt, compact_outline_study, sermon_time_plan


class V32ContextBudgetTests(unittest.TestCase):
    def _large_study(self):
        refs = [f"MAT 14:{verse}" for verse in range(27, 32)]
        translations = [
            {"translation": f"T{i}", "reference": ref, "language": "ko", "text": "가" * 500, "license_note": "test"}
            for ref in refs for i in range(5)
        ]
        context = [
            {"translation": "WEB", "reference": "MAT 14:26", "language": "en", "text": "x" * 500, "license_note": "PD"},
            {"translation": "WEB", "reference": "MAT 14:32", "language": "en", "text": "y" * 500, "license_note": "PD"},
        ]
        notes = [
            {"reference": refs[i % 5], "language": "grc", "lemma": f"lemma{i}", "gloss": "뜻" * 100,
             "morphology": "V-" * 100, "source": "MorphGNT" * 30, "license_note": "CC-BY-SA"}
            for i in range(120)
        ]
        return {"translations": translations, "context": context, "original_notes": notes}, refs

    def test_outline_prompt_spreads_evidence_and_stays_conservative(self):
        study, refs = self._large_study()
        compact = compact_outline_study(study)
        self.assertEqual(len(compact["original_notes"]), 10)
        self.assertTrue(set(refs).issubset({x["reference"] for x in compact["original_notes"]}))
        system, user = build_outline_prompt(
            {"topic": "믿음", "details": "상세" * 2000, "main_reference": "MAT 14:27-31"},
            study, sermon_time_plan(15),
        )
        self.assertLess(len(system) + len(user), 8000)

    def test_sermon_emergency_mode_is_smaller_than_regular_mode(self):
        study, _ = self._large_study()
        doctrine = [{"tradition": "초교파 복음주의", "title": "교리", "section": "", "text": "교리" * 5000,
                     "source_url": "https://example.test", "license_note": "test"} for _ in range(6)]
        payload = {"topic": "믿음", "details": "상세" * 3000, "main_reference": "MAT 14:27-31", "minutes": 15}
        regular = build_sermon_prompt(payload, study["translations"] + study["context"], study["original_notes"], doctrine)
        emergency = build_sermon_prompt({**payload, "_context_compact_level": 2}, study["translations"] + study["context"], study["original_notes"], doctrine)
        self.assertLess(sum(map(len, emergency)), sum(map(len, regular)))
        self.assertLess(sum(map(len, emergency)), 8000)

    def test_lmstudio_context_400_becomes_actionable_korean_error(self):
        body = b'{"error":{"message":"request (9935 tokens) exceeds the available context size (8192 tokens)","type":"exceed_context_size_error","n_prompt_tokens":9935,"n_ctx":8192}}'
        error = urllib.error.HTTPError("http://127.0.0.1:12345/v1/chat/completions", 400, "Bad Request", {}, io.BytesIO(body))
        client = LMStudioClient("http://127.0.0.1:12345/v1")
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(ConnectionError) as raised:
                client.chat("test-model", "system", "user")
        message = str(raised.exception)
        self.assertIn("컨텍스트 한도 초과", message)
        self.assertIn("9935", message)
        self.assertIn("8192", message)


if __name__ == "__main__":
    unittest.main()
