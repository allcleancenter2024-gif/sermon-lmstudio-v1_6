from pathlib import Path
import unittest


class V50OutlineProgressUiTests(unittest.TestCase):
    def test_outline_progress_panel_and_cancel_flow_are_wired(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "templates" / "index.html").read_text(encoding="utf-8")
        script = (root / "static" / "app.js").read_text(encoding="utf-8")
        css = (root / "static" / "v2.css").read_text(encoding="utf-8")
        main = (root / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn('id="outlineProgress"', html)
        self.assertIn('id="cancelOutline"', html)
        self.assertIn('aria-label="3대지 구조 생성 추정 진행률"', html)
        self.assertIn("function startOutlineProgress", script)
        self.assertIn("function cancelOutlineGeneration", script)
        self.assertIn("url.endsWith('/api/outline')", script)
        self.assertIn("X-Generation-Id", script)
        self.assertIn(".outline-progress", css)
        self.assertIn("def create_outline(data: SermonOutlineRequest, request: Request = None)", main)
        self.assertIn("client.begin_generation(request.headers.get(\"X-Generation-Id\", \"\") if request else \"\")", main)

    def test_workflow_rail_buttons_use_the_shared_panel_navigation_and_current_state(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("#workflowRailSteps button[data-target]", script)
        self.assertIn("revealAndScroll(button.dataset.target)", script)
        self.assertIn("button.setAttribute('aria-current','step')", script)


if __name__ == "__main__":
    unittest.main()
