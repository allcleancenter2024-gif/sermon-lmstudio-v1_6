import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.core import init_db
from app.denomination_doctrine import archive_object_key, snapshot_source, validate_official_url


class _Response:
    def __init__(self, body=b"<html>official</html>"):
        self.headers = {"Content-Type": "text/html", "ETag": '"v1"', "Last-Modified": "Wed, 02 Sep 2026 00:00:00 GMT"}
        self._body = body
        self._offset = 0

    def __enter__(self): return self
    def __exit__(self, *_): return False
    def geturl(self): return "https://www.kmc.or.kr/doctrine.html"
    def read(self, limit=-1):
        if limit < 0:
            limit = len(self._body) - self._offset
        chunk = self._body[self._offset:self._offset + limit]
        self._offset += len(chunk)
        return chunk


class _Opener:
    def open(self, request, timeout=20): return _Response()


class DoctrineIngestionTests(unittest.TestCase):
    def test_allowlist_and_ssrf_guards(self):
        self.assertEqual(validate_official_url("https://www.kmc.or.kr/doc"), "https://www.kmc.or.kr/doc")
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            validate_official_url("http://www.kmc.or.kr/doc")
        with self.assertRaisesRegex(ValueError, "허용목록"):
            validate_official_url("https://example.com/doc")
        with self.assertRaisesRegex(ValueError, "사설"):
            validate_official_url("https://127.0.0.1/doc", {"127.0.0.1"})

    def test_archive_key_is_deterministic_and_safe(self):
        key = archive_object_key("KMC", 4, "2025/edition", "a" * 64, "pdf")
        self.assertEqual(key, "doctrine-archive/KMC/4/2025-edition/" + "a" * 64 + "/original.pdf")
        self.assertNotIn("..", key)

    def test_snapshot_creates_document_and_unchanged_second_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "bible.db"
            archive = Path(temp_dir) / "archive"
            init_db(db)
            with closing(sqlite3.connect(db)) as con, con:
                con.execute("INSERT INTO denominations(code,name_ko,active,created_at,updated_at) VALUES('KMC','감리회',1,datetime('now'),datetime('now'))")
                con.execute("""INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,license_status,active,created_at,updated_at) VALUES(1,'교리','https://www.kmc.or.kr/doctrine','OFFICIAL_DENOMINATION','VERIFIED',1,datetime('now'),datetime('now'))""")
            first = snapshot_source(1, db, archive, opener=_Opener())
            second = snapshot_source(1, db, archive, opener=_Opener())
            self.assertTrue(first["changed"])
            self.assertFalse(second["changed"])
            with closing(sqlite3.connect(db)) as con, con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM doctrine_documents").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT status FROM ingestion_jobs ORDER BY id").fetchall(), [("DOWNLOADED",), ("UNCHANGED",)])
            self.assertTrue((archive / first["object_storage_key"].replace("/", "\\")).is_file())


if __name__ == "__main__":
    unittest.main()
