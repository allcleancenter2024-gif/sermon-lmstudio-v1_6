import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.migrations import (
    PHASE1_DATA_MODEL_MIGRATION_ID,
    apply_admin_workflow_migration,
    apply_license_review_migration,
    apply_migrations,
    apply_phase1_data_model_migration,
    rollback_phase1_data_model_migration,
)


class Phase1MigrationRoundtripTests(unittest.TestCase):
    def test_upgrade_downgrade_upgrade_on_empty_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bible.db"
            apply_migrations(path)
            apply_admin_workflow_migration(path)
            apply_license_review_migration(path)
            first = apply_phase1_data_model_migration(path)
            self.assertTrue(first["applied"])
            with closing(sqlite3.connect(path)) as con, con:
                self.assertIn("idempotency_key", [row[1] for row in con.execute("PRAGMA table_info(ingestion_jobs)")])
                self.assertTrue(con.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='uq_ingestion_jobs_active_idempotency'").fetchone())
            self.assertTrue(rollback_phase1_data_model_migration(path)["rolled_back"])
            with closing(sqlite3.connect(path)) as con, con:
                self.assertNotIn("idempotency_key", [row[1] for row in con.execute("PRAGMA table_info(ingestion_jobs)")])
            second = apply_phase1_data_model_migration(path)
            self.assertTrue(second["applied"])
            self.assertEqual(second["migration_id"], PHASE1_DATA_MODEL_MIGRATION_ID)

    def test_downgrade_refuses_existing_phase1_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bible.db"
            apply_migrations(path)
            apply_admin_workflow_migration(path)
            apply_license_review_migration(path)
            apply_phase1_data_model_migration(path)
            with closing(sqlite3.connect(path)) as con, con:
                con.execute("INSERT INTO denominations(code,name_ko,created_at,updated_at) VALUES('T','테스트',datetime('now'),datetime('now'))")
                con.execute("INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,created_at,updated_at) VALUES(1,'자료','https://example.test','OTHER_REFERENCE',datetime('now'),datetime('now'))")
            with self.assertRaisesRegex(RuntimeError, "자동 downgrade"):
                rollback_phase1_data_model_migration(path)


if __name__ == "__main__":
    unittest.main()
