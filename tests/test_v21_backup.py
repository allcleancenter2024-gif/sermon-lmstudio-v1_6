from __future__ import annotations

import asyncio
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import app.main as main
import app.backup as backup_module
from app.backup import BackupError, create_backup, inspect_backup, list_backups, restore_backup
from app.core import init_db


def make_db(path: Path, topic: str = "원본 설교") -> None:
    init_db(path)
    with closing(sqlite3.connect(path)) as con, con:
        con.execute("INSERT INTO sermons(topic, created_at) VALUES(?, '2026-08-08')", (topic,))
        sermon_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute(
            "INSERT INTO sermon_versions(sermon_id, version, content, metadata_json, created_at) VALUES(?,1,?,'{}','2026-08-08')",
            (sermon_id, topic + " 본문"),
        )
        con.execute(
            "INSERT INTO app_settings(key,value_json,updated_at) VALUES('lmstudio_url',?, '2026-08-08')",
            (json.dumps("http://127.0.0.1:12345/v1"),),
        )


def first_topic(path: Path) -> str:
    with closing(sqlite3.connect(path)) as con, con:
        return con.execute("SELECT topic FROM sermons ORDER BY id LIMIT 1").fetchone()[0]


class FakeRequest:
    def __init__(self, content: bytes):
        self.content = content
        self.headers = {"content-length": str(len(content))}

    async def stream(self):
        yield self.content


class V21BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_roundtrip_and_pre_restore_safety(self):
        db, backups = self.root / "data" / "bible.db", self.root / "backups"
        make_db(db, "백업 시점")
        made = create_backup(db, backups, "21.0.0")
        backup_path = backups / made["filename"]
        checked = inspect_backup(backup_path)
        self.assertTrue(checked["ok"])
        self.assertEqual(checked["checks"]["sermons"], 1)
        with closing(sqlite3.connect(db)) as con, con:
            con.execute("UPDATE sermons SET topic='복원 직전'")
        result = restore_backup(backup_path, db, backups, "21.0.0")
        self.assertEqual(first_topic(db), "백업 시점")
        self.assertEqual(result["pre_restore_backup"]["manifest"]["reason"], "pre_restore")
        self.assertEqual(len(list_backups(backups)), 2)

    def test_backup_rejects_foreign_zip_and_path_traversal(self):
        foreign = self.root / "foreign.zip"
        with zipfile.ZipFile(foreign, "w") as archive:
            archive.writestr("hello.txt", "not a backup")
        with self.assertRaises(BackupError):
            inspect_backup(foreign)
        traversal = self.root / "traversal.zip"
        with zipfile.ZipFile(traversal, "w") as archive:
            archive.writestr("../manifest.json", "{}")
            archive.writestr("data/bible.db", b"x")
        with self.assertRaisesRegex(BackupError, "안전하지 않은"):
            inspect_backup(traversal)

    def test_backup_rejects_tampered_database_hash(self):
        db, backups = self.root / "bible.db", self.root / "backups"
        make_db(db)
        made = create_backup(db, backups, "21.0.0")
        original, tampered = backups / made["filename"], self.root / "tampered.zip"
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(tampered, "w") as target:
            target.writestr("manifest.json", source.read("manifest.json"))
            target.writestr("data/bible.db", source.read("data/bible.db") + b"tamper")
        with self.assertRaisesRegex(BackupError, "해시"):
            inspect_backup(tampered)

    def test_backup_closes_every_sqlite_connection_before_temp_cleanup(self):
        db, backups = self.root / "bible.db", self.root / "backups"
        make_db(db)
        real_connect = sqlite3.connect
        opened = []

        class TrackingConnection(sqlite3.Connection):
            was_closed = False

            def close(self):
                self.was_closed = True
                return super().close()

        def tracking_connect(*args, **kwargs):
            kwargs["factory"] = TrackingConnection
            con = real_connect(*args, **kwargs)
            opened.append(con)
            return con

        with patch.object(backup_module.sqlite3, "connect", side_effect=tracking_connect):
            made = create_backup(db, backups, "40.5.0")
            inspect_backup(backups / made["filename"])

        self.assertGreaterEqual(len(opened), 5)
        self.assertTrue(all(con.was_closed for con in opened))

    def test_backup_api_create_download_and_restore_upload(self):
        db, backups = self.root / "data" / "bible.db", self.root / "backups"
        make_db(db, "API 백업")
        with patch.object(main, "DB_PATH", db), patch.object(main, "BACKUPS_DIR", backups):
            created = main.make_backup()
            filename = created["filename"]
            response = main.download_backup(filename)
            self.assertEqual(Path(response.path).name, filename)
            content = (backups / filename).read_bytes()
            self.assertTrue(content.startswith(b"PK"))
            with closing(sqlite3.connect(db)) as con, con:
                con.execute("UPDATE sermons SET topic='API 변경'")
            restored = asyncio.run(main.restore_uploaded_backup(FakeRequest(content), "RESTORE"))
            self.assertEqual(first_topic(db), "API 백업")
            self.assertEqual(restored["pre_restore_backup"]["manifest"]["reason"], "pre_restore")

    def test_restore_api_requires_explicit_confirmation(self):
        with patch.object(main, "BACKUPS_DIR", self.root / "backups"):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.restore_uploaded_backup(FakeRequest(b"PK"), ""))
        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("확인값", raised.exception.detail)


if __name__ == "__main__":
    unittest.main()
