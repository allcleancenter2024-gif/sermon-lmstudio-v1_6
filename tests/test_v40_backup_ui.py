from pathlib import Path
import unittest


class V40BackupUiTests(unittest.TestCase):
    def test_backup_requests_do_not_parse_error_html_as_json(self):
        script = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("async function apiJson", script)
        self.assertIn("apiJson(r,'백업 생성 실패')", script)
        self.assertIn("apiJson(r,'백업 목록 조회 실패')", script)
        self.assertIn("apiJson(r,'복원 실패')", script)
        self.assertIn("서버 창의 상세 오류를 확인하세요", script)


if __name__ == "__main__":
    unittest.main()
