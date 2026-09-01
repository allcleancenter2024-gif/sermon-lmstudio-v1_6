import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.main import RagIndexRequest, SermonRequest, generate_sermon, reindex_rag


class V18ReadinessTests(unittest.TestCase):
    def test_empty_bible_database_blocks_rag_index_before_lmstudio_call(self):
        with (
            patch("app.main.db_stats", return_value={"passages": 0, "translations": 0, "languages": 0}),
            patch("app.main.LMStudioClient") as client,
        ):
            with self.assertRaises(HTTPException) as raised:
                reindex_rag(RagIndexRequest(model="text-embedding-nomic-embed-text-v1.5"))
            self.assertEqual(raised.exception.status_code, 400)
            self.assertIn("성경 자료가 0건", raised.exception.detail)
            client.assert_not_called()

    def test_empty_bible_database_blocks_grounded_sermon_before_lmstudio_call(self):
        with (
            patch("app.main.db_stats", return_value={"passages": 0, "translations": 0, "languages": 0}),
            patch("app.main.LMStudioClient") as client,
        ):
            with self.assertRaises(HTTPException) as raised:
                generate_sermon(SermonRequest(topic="근거 테스트"))
            self.assertEqual(raised.exception.status_code, 400)
            self.assertIn("등록된 성경 근거가 0건", raised.exception.detail)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
