import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.migrations import MIGRATION_ID, apply_migrations, rollback_migration


class DenominationDoctrineMigrationTests(unittest.TestCase):
    def test_additive_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "bible.db"
            self.assertTrue(apply_migrations(db_path)["applied"])
            self.assertFalse(apply_migrations(db_path)["applied"])
            with closing(sqlite3.connect(db_path)) as con, con:
                names = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({"denominations", "doctrine_sources", "doctrine_documents", "doctrine_chunks_v2", "doctrine_embeddings_v2"} <= names)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM schema_migrations WHERE migration_id=?", (MIGRATION_ID,)).fetchone()[0], 1)

    def test_populated_schema_refuses_destructive_rollback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "bible.db"
            apply_migrations(db_path)
            with closing(sqlite3.connect(db_path)) as con, con:
                con.execute("INSERT INTO denominations(code, name_ko, created_at, updated_at) VALUES ('TEST', '테스트 교단', datetime('now'), datetime('now'))")
            with self.assertRaisesRegex(RuntimeError, "자동 삭제 롤백하지 않습니다"):
                rollback_migration(db_path)

    def test_unused_schema_can_roll_back(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "bible.db"
            apply_migrations(db_path)
            self.assertTrue(rollback_migration(db_path)["rolled_back"])


if __name__ == "__main__":
    unittest.main()
