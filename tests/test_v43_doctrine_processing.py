import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.core import init_db
from app.doctrine_processing import DoctrineBlock, chunk_doctrine_blocks, extract_html, process_doctrine_document, quality_gate


class DoctrineProcessingTests(unittest.TestCase):
    def test_html_extraction_removes_navigation_and_preserves_headings(self):
        html = "<nav>광고</nav><h1>제1조 성경</h1><p>" + ("하나님의 말씀과 교회의 신앙을 설명하는 본문입니다. " * 5) + "</p><script>bad()</script>"
        blocks = extract_html(html)
        self.assertEqual(blocks[0].article_number, "1")
        self.assertNotIn("광고", " ".join(x.text for x in blocks))
        self.assertNotIn("bad", " ".join(x.text for x in blocks))
        self.assertTrue(quality_gate(blocks)["passed"])

    def test_chunking_is_deterministic_and_keeps_structure(self):
        blocks = [DoctrineBlock("제1편 > 제1조", "1", "성경", "하나님의 말씀을 믿습니다. " * 80)]
        first = chunk_doctrine_blocks(blocks, target_tokens=100, overlap_tokens=20)
        second = chunk_doctrine_blocks(blocks, target_tokens=100, overlap_tokens=20)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["section_path"], "제1편 > 제1조")
        self.assertEqual(first[0]["content_hash"], first[0]["content_hash"])
        self.assertGreater(len(first), 1)

    def test_process_document_stores_chunks_but_keeps_review_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db = root / "bible.db"
            archive = root / "archive"
            init_db(db)
            key = "doctrine-archive/TEST/1/undated/" + "a" * 64 + "/original.html"
            path = archive / key.replace("/", "\\")
            path.parent.mkdir(parents=True)
            path.write_text("<h1>제1조 고백</h1><p>" + ("교회의 신앙과 실천을 설명하는 충분한 본문입니다. " * 8) + "</p>", encoding="utf-8")
            with closing(sqlite3.connect(db)) as con, con:
                con.execute("INSERT INTO denominations(code,name_ko,created_at,updated_at) VALUES('TEST','테스트',datetime('now'),datetime('now'))")
                con.execute("""INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,license_status,active,created_at,updated_at) VALUES(1,'자료','https://www.kmc.or.kr/x','OFFICIAL_DENOMINATION','VERIFIED',1,datetime('now'),datetime('now'))""")
                con.execute("""INSERT INTO doctrine_documents(source_id,title,content_hash,object_storage_key,mime_type,created_at) VALUES(1,'문서',?,?,'text/html',datetime('now'))""", ('a' * 64, key))
            result = process_doctrine_document(1, db, archive)
            self.assertEqual(result["review_status"], "NEEDS_REVIEW")
            with closing(sqlite3.connect(db)) as con, con:
                self.assertGreater(con.execute("SELECT COUNT(*) FROM doctrine_chunks_v2").fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT active,review_status FROM doctrine_documents WHERE id=1").fetchone(), (0, "NEEDS_REVIEW"))


if __name__ == "__main__":
    unittest.main()
