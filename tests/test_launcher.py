import unittest
from unittest.mock import patch
from pathlib import Path

import launcher
import verify_version
import verify_dependencies


class LauncherSafetyTests(unittest.TestCase):
    def _runtime(self, version="16.0.0"):
        return {
            "app_version": version,
            "supported_minutes": [15, 20, 25, 30, 40],
            "default_minutes": 15,
            "local_url": "http://127.0.0.1:8000",
        }

    def test_runtime_signature_requires_sermon_markers(self):
        self.assertTrue(launcher._is_sermon_runtime(self._runtime()))
        bad = self._runtime()
        bad["local_url"] = "http://127.0.0.1:9999"
        self.assertFalse(launcher._is_sermon_runtime(bad))
        bad = self._runtime()
        bad["supported_minutes"] = [20, 30]
        self.assertFalse(launcher._is_sermon_runtime(bad))

    def test_process_allowlist_is_narrow(self):
        for name in ("python", "python.exe", "pythonw.exe", "SermonLMStudio.exe"):
            self.assertTrue(launcher._allowed_old_server_process(name), name)
        for name in ("chrome.exe", "powershell.exe", "python-helper.exe", ""):
            self.assertFalse(launcher._allowed_old_server_process(name), name)

    def test_version_parser_supports_old_runtime_versions(self):
        self.assertEqual(launcher._version_tuple("38.0.0"), (38, 0, 0))
        self.assertEqual(launcher._version_tuple("V40"), (40, 0, 0))
        self.assertIsNone(launcher._version_tuple("unknown"))

    def test_unverified_port_is_never_terminated(self):
        with (
            patch("launcher._runtime_info", return_value=None),
            patch("launcher._port_in_use", return_value=True),
            patch("builtins.input", return_value=""),
            patch("launcher._stop_windows_pid") as stop_pid,
        ):
            self.assertEqual(launcher.main(), 3)
            stop_pid.assert_not_called()

    def test_same_version_only_opens_browser(self):
        runtime = self._runtime(launcher.APP_VERSION)
        with (
            patch("launcher._runtime_info", return_value=runtime),
            patch("launcher.webbrowser.open") as open_browser,
            patch("launcher._stop_windows_pid") as stop_pid,
        ):
            self.assertEqual(launcher.main(), 0)
            open_browser.assert_called_once_with(launcher.APP_URL)
            stop_pid.assert_not_called()

    def test_listener_change_after_confirmation_aborts_termination(self):
        with (
            patch.object(launcher.os, "name", "nt"),
            patch("launcher._windows_listener_pids", side_effect=[[321], [654]]),
            patch("launcher._windows_process_name", return_value="python"),
            patch("builtins.input", return_value="y"),
            patch("launcher._stop_windows_pid") as stop_pid,
        ):
            self.assertFalse(launcher._offer_to_stop_old_server(self._runtime()))
            stop_pid.assert_not_called()

    def test_verified_older_server_can_be_replaced_without_hidden_prompt(self):
        with (
            patch.object(launcher.os, "name", "nt"),
            patch("launcher._windows_listener_pids", side_effect=[[321], [321]]),
            patch("launcher._windows_process_name", return_value="python"),
            patch("launcher._stop_windows_pid", return_value=True) as stop_pid,
            patch("launcher._port_in_use", return_value=False),
            patch("builtins.input") as prompt,
        ):
            self.assertTrue(launcher._offer_to_stop_old_server(self._runtime("38.0.0"), automatic=True))
            stop_pid.assert_called_once_with(321)
            prompt.assert_not_called()

    def test_newer_running_server_is_never_downgraded(self):
        runtime = self._runtime("99.0.0")
        with (
            patch("launcher._runtime_info", return_value=runtime),
            patch("launcher._offer_to_stop_old_server") as stop_offer,
        ):
            self.assertEqual(launcher.main(), 5)
            stop_offer.assert_not_called()

    def test_windows_source_launcher_has_package_version_guards(self):
        root = Path(__file__).resolve().parents[1]
        start = (root / "start.bat").read_text(encoding="utf-8")
        run_v40 = (root / "RUN_V40.bat").read_text(encoding="utf-8")
        self.assertEqual((root / "VERSION.txt").read_text(encoding="utf-8").strip(), launcher.APP_VERSION)
        self.assertIn('VERSION.txt', start)
        self.assertIn('set "EXPECTED_VERSION=%%V"', start)
        self.assertIn('verify_version.py "%EXPECTED_VERSION%"', start)
        self.assertIn('verify_dependencies.py --check', start)
        self.assertIn('verify_dependencies.py --write', start)
        self.assertIn('Skipping pip installation', start)
        self.assertNotIn('ACTUAL_VERSION', start)
        self.assertIn('for /f', start.lower())
        self.assertIn('different application version', start)
        self.assertIn('VERSION.txt', run_v40)
        self.assertIn('call start.bat', run_v40)
        build = (root / "build_windows.bat").read_text(encoding="utf-8")
        self.assertNotIn('for /f', build.lower())
        self.assertIn('--collect-all reportlab', build)
        self.assertIn('--exclude-module weasyprint', build)

    def test_version_verifier_accepts_current_application(self):
        self.assertEqual(verify_version.verify(launcher.APP_VERSION), 0)

    def test_version_verifier_rejects_mixed_application(self):
        self.assertEqual(verify_version.verify("38.0.0"), 6)

    def test_dependency_stamp_tracks_requirement_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            stamp = Path(tmp) / "requirements.sha256"
            self.assertFalse(verify_dependencies.dependencies_current(stamp))
            self.assertEqual(verify_dependencies.write_stamp(stamp), 0)
            self.assertTrue(verify_dependencies.dependencies_current(stamp))


if __name__ == "__main__":
    unittest.main()
