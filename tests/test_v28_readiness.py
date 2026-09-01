import unittest
from unittest.mock import patch
from pathlib import Path

import launcher
from app import main


class _ReadyClient:
    def model_catalog(self):
        return {
            "models": ["local-generation"],
            "generation_models": ["local-generation"],
            "embedding_models": ["local-embedding"],
            "source": "openai_compatible",
        }


class V28ReadinessTests(unittest.TestCase):
    def test_workflow_config_version_and_15_minute_default_match_runtime(self):
        config = main.workflow_config()
        self.assertEqual(config["version"], 40)
        self.assertEqual(config["app_version"], "40.9.10")
        self.assertEqual(config["default_minutes"], 15)
        self.assertIn(15, config["minutes"])

    def test_readiness_distinguishes_generation_from_pdf_output(self):
        with (
            patch.object(main, "LMStudioClient", return_value=_ReadyClient()),
            patch.object(main, "db_stats", return_value={"passages": 10}),
            patch.object(main, "rag_stats", return_value={"models": [], "indexed": 0}),
            patch.object(main, "pdf_environment_status", return_value={
                "ready": False, "engine_ready": True, "font_ready": False, "engine_error": ""
            }),
            patch.object(main.os, "access", return_value=True),
        ):
            result = main.runtime_readiness()
        self.assertTrue(result["ready_for_generation"])
        self.assertFalse(result["ready_for_full_output"])
        self.assertEqual(next(x for x in result["steps"] if x["key"] == "pdf")["state"], "warn")

    def test_windows_pdf_fallback_is_packaged(self):
        root = Path(__file__).resolve().parents[1]
        requirements = (root / "requirements-pdf.txt").read_text(encoding="utf-8").lower()
        self.assertIn("weasyprint", requirements)
        self.assertIn("reportlab", requirements)
        with (
            patch.object(main, "LMStudioClient", return_value=_ReadyClient()),
            patch.object(main, "db_stats", return_value={"passages": 10}),
            patch.object(main, "rag_stats", return_value={"models": [], "indexed": 0}),
            patch.object(main, "pdf_environment_status", return_value={
                "ready": True, "engine_ready": True, "font_ready": True,
                "engine": "reportlab", "font_family": "Malgun Gothic", "engine_error": "WeasyPrint unavailable"
            }),
            patch.object(main.os, "access", return_value=True),
        ):
            result = main.runtime_readiness()
        pdf_step = next(x for x in result["steps"] if x["key"] == "pdf")
        self.assertEqual(pdf_step["state"], "pass")
        self.assertIn("ReportLab", pdf_step["detail"])
        self.assertIn("Malgun Gothic", pdf_step["detail"])

    def test_zip_runtime_warns_to_backup_before_update(self):
        with (
            patch.object(main, "LMStudioClient", return_value=_ReadyClient()),
            patch.object(main, "db_stats", return_value={"passages": 10}),
            patch.object(main, "rag_stats", return_value={"models": [], "indexed": 0}),
            patch.object(main, "pdf_environment_status", return_value={
                "ready": True, "engine_ready": True, "font_ready": True,
                "engine": "reportlab", "font_family": "Malgun Gothic", "engine_error": ""
            }),
            patch.object(main.sys, "frozen", False, create=True),
            patch.object(main.os, "access", return_value=True),
        ):
            result = main.runtime_readiness()
        portability = next(x for x in result["steps"] if x["key"] == "data_portability")
        self.assertEqual(portability["state"], "warn")
        self.assertIn("통합 백업", portability["detail"])

    def test_readiness_blocks_generation_when_bible_db_is_empty(self):
        with (
            patch.object(main, "LMStudioClient", return_value=_ReadyClient()),
            patch.object(main, "db_stats", return_value={"passages": 0}),
            patch.object(main, "rag_stats", return_value={"models": []}),
            patch.object(main, "pdf_environment_status", return_value={
                "ready": True, "engine_ready": True, "font_ready": True, "engine_error": ""
            }),
            patch.object(main.os, "access", return_value=True),
        ):
            result = main.runtime_readiness()
        self.assertFalse(result["ready_for_generation"])
        self.assertGreaterEqual(result["required_failures"], 1)

    def test_launcher_version_mode_does_not_start_server(self):
        with patch.object(launcher.sys, "argv", ["SermonLMStudio.exe", "--version"]), patch("launcher.uvicorn.run") as run:
            self.assertEqual(launcher.main(), 0)
            run.assert_not_called()

    def test_launcher_diagnose_uses_readiness_exit_code(self):
        report = {"ready_for_generation": False, "steps": [], "user_data_root": "data", "lmstudio_url": "http://127.0.0.1:12345/v1"}
        with patch.object(launcher.sys, "argv", ["SermonLMStudio.exe", "--diagnose"]), patch("launcher.runtime_readiness", return_value=report):
            self.assertEqual(launcher.main(), 4)


if __name__ == "__main__":
    unittest.main()
