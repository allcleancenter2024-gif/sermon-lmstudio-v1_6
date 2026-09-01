from pathlib import Path
import unittest


class V41GenerationProgressUiTests(unittest.TestCase):
    def test_generation_progress_panel_is_attached_to_generation_flow(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "templates" / "index.html").read_text(encoding="utf-8")
        script = (root / "static" / "app.js").read_text(encoding="utf-8")
        css = (root / "static" / "v2.css").read_text(encoding="utf-8")
        self.assertIn('id="generationProgress"', html)
        self.assertIn('role="progressbar"', html)
        self.assertIn("function startGenerationProgress", script)
        self.assertIn("progress.finish()", script)
        self.assertIn("progress.fail(e.message)", script)
        self.assertIn(".generation-progress", css)
        self.assertIn("추정 진행률", html)


if __name__ == "__main__":
    unittest.main()
