import unittest
from pathlib import Path

from app import main
from app.version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class V37FirstRunWizardTests(unittest.TestCase):
    def test_runtime_version_and_default_duration(self):
        config = main.workflow_config()
        self.assertEqual(config["version"], 40)
        self.assertEqual(config["app_version"], APP_VERSION)
        self.assertEqual(config["default_minutes"], 15)
        self.assertEqual(config["minutes"], [15, 20, 25, 30])

    def test_first_run_wizard_has_single_next_action(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="firstRunSteps"', html)
        self.assertIn('id="firstRunNext"', html)
        self.assertIn('id="firstRunRefresh"', html)
        self.assertIn("RAG·PDF·원어 사전은 보완 기능", html)

    def test_wizard_reuses_health_state_and_requires_openai_compatible_generation(self):
        js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function renderFirstRunSetup(d=lastHealth)", js)
        self.assertIn("d.source==='openai_compatible'", js)
        self.assertNotIn("fetch('/api/setup", js)
        self.assertIn("renderFirstRunSetup(d)", js)


if __name__ == "__main__":
    unittest.main()
