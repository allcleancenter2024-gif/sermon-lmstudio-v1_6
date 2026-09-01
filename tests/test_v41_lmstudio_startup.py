import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from app import lmstudio_control
from app import main


class LMStudioStartupTests(unittest.TestCase):
    def test_loaded_model_ids_reads_lms_ps_json(self):
        payload = {"models": [{"identifier": "qwen/qwen3.6-27b"}, {"modelKey": "text-embedding-nomic-embed-text-v1.5"}]}
        result = Mock(returncode=0, stdout=json.dumps(payload), stderr="")
        with (
            patch("app.lmstudio_control.find_lms_cli", return_value=Path("lms.exe")),
            patch("app.lmstudio_control.subprocess.run", return_value=result) as run,
        ):
            ids = lmstudio_control.loaded_model_ids()
        self.assertEqual(ids, {"qwen/qwen3.6-27b", "text-embedding-nomic-embed-text-v1.5"})
        self.assertEqual(run.call_args.args[0][-2:], ["ps", "--json"])
    def test_local_api_port_accepts_only_local_http(self):
        self.assertEqual(lmstudio_control.local_api_port("http://127.0.0.1:12345/v1"), 12345)
        self.assertEqual(lmstudio_control.local_api_port("http://localhost:4321/v1"), 4321)
        with self.assertRaises(ValueError):
            lmstudio_control.local_api_port("http://192.168.0.2:12345/v1")
        with self.assertRaises(ValueError):
            lmstudio_control.local_api_port("https://127.0.0.1:12345/v1")

    def test_start_reports_missing_cli_without_running_anything(self):
        with (
            patch("app.lmstudio_control.port_is_open", return_value=False),
            patch("app.lmstudio_control.find_lms_cli", return_value=None),
            patch("app.lmstudio_control.subprocess.Popen") as run,
        ):
            result = lmstudio_control.start_local_server("http://127.0.0.1:12345/v1")
        self.assertFalse(result["port_open"])
        self.assertIn("찾지 못했습니다", result["message"])
        run.assert_not_called()

    def test_start_uses_exact_local_port_and_official_cli(self):
        fake = Mock()
        fake.poll.return_value = None
        with (
            patch("app.lmstudio_control.find_lms_cli", return_value=Path("C:/Users/test/.lmstudio/bin/lms.exe")),
            patch("app.lmstudio_control.port_is_open", side_effect=[False, True]),
            patch("app.lmstudio_control.subprocess.Popen", return_value=fake) as run,
        ):
            result = lmstudio_control.start_local_server("http://127.0.0.1:12345/v1", wait_seconds=1)
        self.assertTrue(result["started"])
        run.assert_called_once()
        args = run.call_args.args[0]
        self.assertEqual(args[-6:], ["server", "start", "--port", "12345", "--bind", "127.0.0.1"])
        self.assertNotIn("--cors", args)

    def test_failed_cli_returns_immediately_without_full_wait(self):
        fake = Mock()
        fake.poll.return_value = 2
        with (
            patch("app.lmstudio_control.find_lms_cli", return_value=Path("C:/Users/test/.lmstudio/bin/lms.exe")),
            patch("app.lmstudio_control.port_is_open", return_value=False),
            patch("app.lmstudio_control.subprocess.Popen", return_value=fake),
            patch("app.lmstudio_control.time.sleep") as sleep,
        ):
            result = lmstudio_control.start_local_server("http://127.0.0.1:12345/v1", wait_seconds=12)
        self.assertFalse(result["port_open"])
        self.assertIn("종료 코드 2", result["message"])
        sleep.assert_not_called()

    def test_timed_out_helper_process_is_cleaned_up(self):
        fake = Mock()
        fake.poll.return_value = None
        with (
            patch("app.lmstudio_control.find_lms_cli", return_value=Path("C:/Users/test/.lmstudio/bin/lms.exe")),
            patch("app.lmstudio_control.port_is_open", return_value=False),
            patch("app.lmstudio_control.subprocess.Popen", return_value=fake),
            patch("app.lmstudio_control.time.monotonic", side_effect=[0.0, 2.0]),
        ):
            result = lmstudio_control.start_local_server("http://127.0.0.1:12345/v1", wait_seconds=1)
        self.assertFalse(result["port_open"])
        fake.terminate.assert_called_once()
        fake.wait.assert_called_once_with(timeout=2)

    def test_diagnostics_distinguishes_stopped_server(self):
        with (
            patch("app.main.get_lmstudio_url", return_value="http://127.0.0.1:12345/v1"),
            patch("app.main.find_lms_cli", return_value=Path("lms.exe")),
            patch("app.main.port_is_open", return_value=False),
        ):
            result = main.lmstudio_diagnostics()
        self.assertEqual(result["cause"], "server_stopped")
        self.assertFalse(result["ok"])

    def test_start_endpoint_never_loads_or_substitutes_model(self):
        with (
            patch("app.main.get_lmstudio_url", return_value="http://127.0.0.1:12345/v1"),
            patch("app.main.start_local_server", return_value={"started": True, "port_open": True, "port": 12345, "cli": "lms.exe", "message": "started"}),
            patch("app.main.LMStudioClient") as client,
        ):
            client.return_value.model_catalog.return_value = {"source": "openai_compatible", "generation_models": ["model-a"]}
            result = main.start_lmstudio_server()
        self.assertTrue(result["api_ready"])
        self.assertEqual(result["generation_models"], ["model-a"])


if __name__ == "__main__":
    unittest.main()
