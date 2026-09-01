from pathlib import Path
import unittest


class NotebookLmUiTests(unittest.TestCase):
    def test_four_step_ui_and_safe_json_parser_are_present(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "templates" / "index.html").read_text(encoding="utf-8")
        script = (root / "static" / "app.js").read_text(encoding="utf-8")
        for text in ("자료 확인", "자료팩 만들기", "Notebook에서 연구", "결과 가져오기"):
            self.assertIn(text, html)
        self.assertIn("apiJson(r,'Notebook 자료팩 생성 실패')", script)
        self.assertIn("apiJson(r,'연구 결과 가져오기 실패')", script)
        self.assertIn("성경·원어 DB에 합쳐지지 않고", html)
        self.assertIn('id="recoverLmStudio"', html)
        self.assertIn("/api/lmstudio/recover", script)


if __name__ == "__main__":
    unittest.main()
