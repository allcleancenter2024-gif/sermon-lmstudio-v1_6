import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.core import init_db
from app.doctrine_rag import build_approved_doctrine_index, search_approved_doctrine


class _FakeEmbeddings:
    def embeddings(self, model, inputs):
        return [[1.0, 0.0] if "사랑" in text else [0.0, 1.0] for text in inputs]


class DoctrineRagTests(unittest.TestCase):
    def test_index_and_search_are_approval_and_denomination_isolated(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "bible.db"
            init_db(db)
            with closing(sqlite3.connect(db)) as con, con:
                for code in ("A", "B", "COMMON"):
                    con.execute("INSERT INTO denominations(code,name_ko,created_at,updated_at) VALUES(?,?,datetime('now'),datetime('now'))", (code, code))
                for denom_id, title in ((1, "A자료"), (2, "B자료"), (3, "공통자료")):
                    con.execute("""INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,license_status,active,created_at,updated_at) VALUES(?,?,?,'OFFICIAL_DENOMINATION','VERIFIED',1,datetime('now'),datetime('now'))""", (denom_id, title, "https://www.kmc.or.kr/x"))
                    con.execute("""INSERT INTO doctrine_documents(source_id,title,content_hash,review_status,active,created_at) VALUES(?,?,?,'APPROVED',1,datetime('now'))""", (denom_id, title, str(denom_id) * 64))
                    con.execute("""INSERT INTO doctrine_chunks_v2(document_id,section_path,chunk_index,content,content_hash) VALUES(?,?,?,?,?)""", (denom_id, "제1조", 0, "사랑의 교리" if denom_id != 2 else "다른 교단", chr(96 + denom_id) * 64))
            built = build_approved_doctrine_index(_FakeEmbeddings(), "fake-model", db)
            self.assertEqual(built["indexed"], 3)
            items = search_approved_doctrine("사랑", _FakeEmbeddings(), "fake-model", "A", db)
            self.assertEqual({x["denomination_code"] for x in items}, {"A", "COMMON"})
            self.assertNotIn("B자료", {x["document_title"] for x in items})
            self.assertEqual(search_approved_doctrine("사랑", _FakeEmbeddings(), "fake-model", "UNKNOWN", db, include_common=False), [])
            again = build_approved_doctrine_index(_FakeEmbeddings(), "fake-model", db)
            self.assertEqual(again["indexed"], 3)

    def test_pending_document_is_never_indexed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "bible.db"
            init_db(db)
            self.assertEqual(build_approved_doctrine_index(_FakeEmbeddings(), "fake-model", db)["indexed"], 0)


if __name__ == "__main__":
    unittest.main()
