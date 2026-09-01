from contextlib import closing
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.core import import_items, init_db, register_translation_license


class V29ImportResilienceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "bible.db"
        init_db(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def test_large_batch_and_retry_are_idempotent(self):
        items = [
            {"translation": "WEB", "language": "en", "reference": f"TST 1:{i}", "text": f"Verse {i}", "license_note": "Public Domain"}
            for i in range(1, 5001)
        ]
        self.assertEqual(import_items(items, self.db), 5000)
        self.assertEqual(import_items(items, self.db), 5000)
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM passages WHERE translation='WEB'").fetchone()[0], 5000)

    def test_blocked_license_rejects_entire_batch_before_writes(self):
        register_translation_license({
            "translation": "BLOCKED", "license_status": "restricted", "allow_fulltext": False,
            "copyright_holder": "holder", "permission_ref": "", "source_url": "", "notes": "",
        }, self.db)
        items = [
            {"translation": "WEB", "reference": "TST 1:1", "text": "Allowed"},
            {"translation": "BLOCKED", "reference": "TST 1:2", "text": "Denied"},
        ]
        with self.assertRaisesRegex(ValueError, "전문 저장"):
            import_items(items, self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM passages").fetchone()[0], 0)

    def test_reimport_invalidates_stale_rag_vector(self):
        item = {"translation": "WEB", "language": "en", "reference": "TST 1:1", "text": "Old text"}
        import_items([item], self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            passage_id = con.execute("SELECT id FROM passages WHERE translation='WEB' AND reference='TST 1:1'").fetchone()[0]
            con.execute(
                "INSERT INTO rag_embeddings(passage_id, model, vector_json, dimension) VALUES(?, ?, ?, ?)",
                (passage_id, "embed-test", "[1.0, 0.0]", 2),
            )
        import_items([{**item, "text": "Updated text"}], self.db)
        with closing(sqlite3.connect(self.db)) as con, con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM rag_embeddings WHERE passage_id=?", (passage_id,)).fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT text FROM passages WHERE id=?", (passage_id,)).fetchone()[0], "Updated text")


if __name__ == "__main__":
    unittest.main()
