import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.auth import create_user, is_admin
from app.core import init_db
from app.doctrine_workflow import fetch_indexable_doctrine_chunks, transition_document


class DoctrineWorkflowTests(unittest.TestCase):
    def test_first_user_is_admin_and_later_users_are_not(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            auth_db = Path(temp_dir) / "auth.sqlite3"
            self.assertTrue(create_user(auth_db, "first", "long-password-1"))
            self.assertTrue(create_user(auth_db, "second", "long-password-2"))
            self.assertTrue(is_admin(auth_db, "first"))
            self.assertFalse(is_admin(auth_db, "second"))

    def test_only_approved_active_documents_are_indexable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "bible.db"
            init_db(db)
            with closing(sqlite3.connect(db)) as con, con:
                con.execute("INSERT INTO denominations(code,name_ko,created_at,updated_at) VALUES('T','테스트',datetime('now'),datetime('now'))")
                con.execute("""INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,license_status,active,created_at,updated_at) VALUES(1,'자료','https://www.kmc.or.kr/x','OFFICIAL_DENOMINATION','VERIFIED',1,datetime('now'),datetime('now'))""")
                con.execute("""INSERT INTO doctrine_documents(source_id,title,content_hash,review_status,active,created_at) VALUES(1,'문서','%s','NEEDS_REVIEW',0,datetime('now'))""" % ('a' * 64))
                con.execute("""INSERT INTO doctrine_chunks_v2(document_id,section_path,chunk_index,content,content_hash) VALUES(1,'제1조',0,'본문','%s')""" % ('b' * 64))
            self.assertEqual(fetch_indexable_doctrine_chunks(db), [])
            result = transition_document(1, "APPROVED", "reviewer", "확인 완료", db)
            self.assertTrue(result["active"])
            self.assertEqual(len(fetch_indexable_doctrine_chunks(db)), 1)
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute("SELECT action,from_status,to_status FROM doctrine_audit_log").fetchone(), ("status_change", "NEEDS_REVIEW", "APPROVED"))

    def test_approval_without_chunks_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "bible.db"
            init_db(db)
            with closing(sqlite3.connect(db)) as con, con:
                con.execute("INSERT INTO denominations(code,name_ko,created_at,updated_at) VALUES('T','테스트',datetime('now'),datetime('now'))")
                con.execute("""INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,license_status,active,created_at,updated_at) VALUES(1,'자료','https://www.kmc.or.kr/x','OFFICIAL_DENOMINATION','VERIFIED',1,datetime('now'),datetime('now'))""")
                con.execute("""INSERT INTO doctrine_documents(source_id,title,content_hash,review_status,created_at) VALUES(1,'문서','%s','NEEDS_REVIEW',datetime('now'))""" % ('a' * 64))
            with self.assertRaisesRegex(ValueError, "청크가 없는 문서"):
                transition_document(1, "APPROVED", "reviewer", db_path=db)


if __name__ == "__main__":
    unittest.main()
