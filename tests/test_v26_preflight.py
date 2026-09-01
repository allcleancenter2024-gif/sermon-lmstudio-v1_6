from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

import app.main as main
from app.main import PreflightRequest, SermonRequest


class V26PreflightTests(unittest.TestCase):
    def _packet(self):
        return {
            "readiness": {"generation_ready": True, "original_language_ready": False, "doctrine_ready": False},
            "missing_main_references": [], "original_risk_flags": [],
            "evidence_completeness": {"score": 50, "label": "자료 보강 필요"},
            "study": {},
        }

    def test_preflight_default_sermon_time_is_fifteen_minutes(self):
        self.assertEqual(PreflightRequest().minutes, 15)

    def test_preflight_required_conditions_can_pass_with_optional_warnings(self):
        client = Mock()
        client.model_catalog.return_value = {
            "source": "openai_compatible", "generation_models": ["gemma"], "embedding_models": []
        }
        with (
            patch("app.main.db_stats", return_value={"passages": 10}),
            patch("app.main.rag_stats", return_value={"models": [], "doctrine_models": []}),
            patch("app.main.LMStudioClient", return_value=client),
            patch("app.main._collect_research_packet", return_value=self._packet()),
        ):
            result = main.preflight_check(PreflightRequest(topic="믿음", main_reference="MAT 14:27", model="gemma", use_rag=False))
        self.assertTrue(result["ready"])
        self.assertEqual(result["required_failures"], 0)
        self.assertGreaterEqual(result["warnings"], 1)

    def test_preflight_blocks_missing_main_reference(self):
        client = Mock()
        client.model_catalog.return_value = {
            "source": "openai_compatible", "generation_models": ["gemma"], "embedding_models": []
        }
        with (
            patch("app.main.db_stats", return_value={"passages": 10}),
            patch("app.main.rag_stats", return_value={"models": [], "doctrine_models": []}),
            patch("app.main.LMStudioClient", return_value=client),
            patch("app.main._collect_research_packet") as collect,
        ):
            result = main.preflight_check(PreflightRequest(topic="믿음", model="gemma", use_rag=False))
        self.assertFalse(result["ready"])
        self.assertTrue(any(x["key"] == "main_reference" and x["state"] == "fail" for x in result["steps"]))
        collect.assert_not_called()

    def test_selected_unloaded_generation_model_is_not_silently_replaced(self):
        client = Mock()
        client.model_catalog.return_value = {
            "source": "openai_compatible", "generation_models": ["ready-model"], "embedding_models": []
        }
        with self.assertRaisesRegex(RuntimeError, "READY 목록"):
            main._select_generation_model(client, "stale-model")

    def test_direct_sermon_api_also_requires_main_reference_before_lmstudio(self):
        with (
            patch("app.main.db_stats", return_value={"passages": 10}),
            patch("app.main.LMStudioClient") as client_cls,
        ):
            with self.assertRaises(HTTPException) as raised:
                main.generate_sermon(SermonRequest(topic="믿음"))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("중심본문", raised.exception.detail)
        client_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
