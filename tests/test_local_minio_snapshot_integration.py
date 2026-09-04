import hashlib
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import pytest

from app.core import init_db
from app.denomination_doctrine import snapshot_source
from app.doctrine_processing import process_doctrine_document
from app.doctrine_storage import MinioObjectStore
from app.doctrine_storage_audit import audit_minio_references


pytestmark = pytest.mark.integration


class _Response:
    status = 200
    headers = {"Content-Type": "text/html", "ETag": '"local-v1"'}
    body = b"<html><h1>Local official test</h1><p>" + (b"This is a sufficiently long approved test source. " * 4) + b"</p></html>"

    def __init__(self):
        self._used = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def geturl(self):
        return "https://www.kmc.or.kr/local-test.html"

    def read(self, _limit=-1):
        if self._used:
            return b""
        self._used = True
        return self.body


class _Opener:
    def open(self, _request, timeout=20):
        return _Response()


def test_real_local_minio_snapshot_and_audit():
    if os.environ.get("RUN_LOCAL_MINIO_SNAPSHOT") != "1":
        pytest.skip("명시적 로컬 MinIO snapshot 통합시험 플래그가 없어 건너뜁니다.")
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        db = root / "bible.db"
        archive = root / "archive"
        init_db(db)
        with closing(sqlite3.connect(db)) as con, con:
            con.execute("INSERT INTO denominations(code,name_ko,active,created_at,updated_at) VALUES('KMC','감리회',1,datetime('now'),datetime('now'))")
            con.execute("INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,license_status,active,created_at,updated_at) VALUES(1,'로컬 테스트','https://www.kmc.or.kr/local-test','OFFICIAL_DENOMINATION','VERIFIED',1,datetime('now'),datetime('now'))")
        result = snapshot_source(1, db, archive, opener=_Opener())
        assert result["changed"] is True
        assert result["object_storage_key"].startswith("doctrine-archive/KMC/1/")
        store = MinioObjectStore.from_env()
        with closing(sqlite3.connect(db)) as con, con:
            key = con.execute("SELECT object_storage_key FROM doctrine_documents WHERE id=?", (result["document_id"],)).fetchone()[0]
            snapshot = con.execute("SELECT sha256_verified,content_length,final_url FROM source_snapshots WHERE document_id=?", (result["document_id"],)).fetchone()
        assert key == result["object_storage_key"]
        assert snapshot[0:2] == (1, len(_Response.body))
        assert snapshot[2].startswith("https://www.kmc.or.kr/")
        assert store.verify("production/" + key, result["content_hash"])
        processed = process_doctrine_document(result["document_id"], db, archive, object_store=store, object_prefix="production")
        assert processed["review_status"] == "NEEDS_REVIEW"
        assert processed["chunks"] > 0
        audit = audit_minio_references(store, [key.removeprefix("doctrine-archive/")], prefix="production/doctrine-archive/")
        assert audit["missing_objects"] == []
