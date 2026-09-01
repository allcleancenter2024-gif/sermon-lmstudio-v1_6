from pathlib import Path
import unittest


class V42RagProgressUiTests(unittest.TestCase):
    def test_rag_progress_panel_is_connected_to_success_and_failure_paths(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "templates" / "index.html").read_text(encoding="utf-8")
        script = (root / "static" / "app.js").read_text(encoding="utf-8")
        css = (root / "static" / "v2.css").read_text(encoding="utf-8")
        self.assertIn('id="ragProgress"', html)
        self.assertIn('aria-label="RAG 인덱스 추정 진행률"', html)
        self.assertIn("function startRagProgress", script)
        self.assertIn("progress.finish(d)", script)
        self.assertIn("progress.fail(e.message)", script)
        self.assertIn("성경 본문을 벡터화하고 있습니다", script)
        self.assertIn(".rag-progress", css)


if __name__ == "__main__":
    unittest.main()
