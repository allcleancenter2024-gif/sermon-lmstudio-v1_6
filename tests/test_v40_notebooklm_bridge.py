from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.core import init_db
from app.notebooklm import (
    PACK_FORMAT,
    create_pack,
    drive_status,
    import_research_note,
    init_notebooklm_db,
    list_research_notes,
    set_drive_folder,
)


class NotebookLmBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "data" / "bible.db"
        init_db(self.db)
        init_notebooklm_db(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def packet(self):
        return {
            "readiness": {"generation_ready": True},
            "study": {
                "translations": [{"translation": "WEB", "reference": "JHN 3:16", "text": "For God so loved...", "license_note": "Public Domain"}],
                "original_notes": [{"reference": "JHN 3:16", "language": "grc", "lemma": "ἀγαπάω", "gloss": "사랑하다", "source": "test", "license_note": "test license"}],
                "note_markdown": "# 연구 노트\n",
            },
            "doctrine_sources": [{"title": "신앙고백", "section": "1", "text": "등록 교리 근거", "source_url": "https://example.test", "license_note": "test"}],
        }

    def test_pack_is_valid_and_drive_copy_is_hash_identical(self):
        drive = self.root / "My Drive"
        drive.mkdir()
        set_drive_folder(str(drive), self.db)
        result = create_pack(self.packet(), topic="하나님의 사랑", reference="JHN 3:16", minutes=15,
                             tradition="초교파 복음주의", exports_dir=self.root / "exports",
                             db_path=self.db, sync_to_drive=True)
        local = Path(result["path"])
        copied = Path(result["drive_path"])
        self.assertTrue(local.is_file())
        self.assertEqual(local.read_bytes(), copied.read_bytes())
        with zipfile.ZipFile(local) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["format"], PACK_FORMAT)
            self.assertIn("05_연구질문.md", archive.namelist())
            self.assertIn("등록 교리 근거", archive.read("04_교리주석.md").decode("utf-8"))

    def test_drive_failure_does_not_block_local_pack(self):
        result = create_pack(self.packet(), topic="사랑", reference="JHN 3:16", minutes=20,
                             tradition="초교파 복음주의", exports_dir=self.root / "exports",
                             db_path=self.db, sync_to_drive=True)
        self.assertTrue(Path(result["path"]).is_file())
        self.assertFalse(result["drive_path"])
        self.assertTrue(result["drive_warning"])

    def test_external_note_is_separate_and_citations_are_only_a_review_signal(self):
        result = import_research_note(reference="JHN 3:16", title="연구", content="사랑의 의미입니다 [1] 출처: WEB",
                                      sermon_id=None, db_path=self.db)
        self.assertEqual(result["verification_status"], "needs_review")
        notes = list_research_notes("JHN 3:16", self.db)
        self.assertEqual(len(notes), 1)
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM passages").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM original_word_notes").fetchone()[0], 0)

    def test_unc_drive_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "네트워크 공유"):
            set_drive_folder(r"\\server\share", self.db)

    def test_drive_status_survives_missing_folder(self):
        drive = self.root / "My Drive"
        drive.mkdir()
        set_drive_folder(str(drive), self.db)
        drive.rmdir()
        self.assertFalse(drive_status(self.db)["ready"])


if __name__ == "__main__":
    unittest.main()
