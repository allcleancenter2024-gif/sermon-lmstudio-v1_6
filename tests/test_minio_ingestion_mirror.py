import hashlib
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from minio.error import S3Error

from app.core import init_db
from app.denomination_doctrine import snapshot_source


class _Response:
    def __init__(self, body): self.body = body
    def read(self): return self.body
    def close(self): pass
    def release_conn(self): pass


class _FakeMinio:
    objects = {}
    def __init__(self, *_args, **_kwargs): pass
    def bucket_exists(self, _bucket): return True
    def get_object(self, _bucket, key):
        if key not in self.objects:
            raise S3Error(None, "NoSuchKey", "missing", key, "", "")
        return _Response(self.objects[key])
    def put_object(self, _bucket, key, stream, length, **_kwargs):
        self.objects[key] = stream.read(length)


class _HttpResponse:
    headers = {"Content-Type": "text/html", "ETag": '"v1"'}
    status = 200
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def geturl(self): return "https://www.kmc.or.kr/doctrine.html"
    def read(self, _limit=-1):
        body = b"<html>official</html>"
        if hasattr(self, "used"): return b""
        self.used = True
        return body


class _Opener:
    def open(self, _request, timeout=20): return _HttpResponse()


class MinioIngestionMirrorTests(unittest.TestCase):
    def test_enabled_snapshot_mirrors_original_and_metadata_under_production_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch("minio.Minio", _FakeMinio):
            db = Path(temp_dir) / "bible.db"
            archive = Path(temp_dir) / "archive"
            init_db(db)
            with closing(sqlite3.connect(db)) as con, con:
                con.execute("INSERT INTO denominations(code,name_ko,active,created_at,updated_at) VALUES('KMC','감리회',1,datetime('now'),datetime('now'))")
                con.execute("INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,license_status,active,created_at,updated_at) VALUES(1,'교리','https://www.kmc.or.kr/doctrine','OFFICIAL_DENOMINATION','VERIFIED',1,datetime('now'),datetime('now'))")
            old = {key: os.environ.get(key) for key in ("MINIO_ENABLED", "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY", "MINIO_BUCKET")}
            os.environ.update({"MINIO_ENABLED": "true", "MINIO_ENDPOINT": "http://127.0.0.1:9000", "MINIO_ACCESS_KEY": "test", "MINIO_SECRET_KEY": "test-secret", "MINIO_BUCKET": "sermon-documents"})
            try:
                result = snapshot_source(1, db, archive, opener=_Opener())
            finally:
                for key, value in old.items():
                    if value is None: os.environ.pop(key, None)
                    else: os.environ[key] = value
            prefix = "production/" + result["object_storage_key"]
            metadata = prefix.rsplit("/", 1)[0] + "/metadata.json"
            self.assertIn(prefix, _FakeMinio.objects)
            self.assertIn(metadata, _FakeMinio.objects)
            self.assertEqual(hashlib.sha256(_FakeMinio.objects[prefix]).hexdigest(), result["content_hash"])


if __name__ == "__main__": unittest.main()
