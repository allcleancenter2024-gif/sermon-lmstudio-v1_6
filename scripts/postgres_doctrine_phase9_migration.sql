-- Phase 9 Doctrine/Evidence PostgreSQL migration gate.
--
-- This file is intentionally not executed by application startup. Run it only
-- after a production backup, a dry-run, and explicit cutover approval.
-- The two base schema files must be applied before this migration.
-- No source documents, chunks, or embeddings are copied by this file.

BEGIN;

CREATE TABLE IF NOT EXISTS doctrine_schema_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    application_version TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

-- Repair an older candidate schema additively. IF NOT EXISTS makes retries safe.
ALTER TABLE doctrine_chunks_v2 ADD COLUMN IF NOT EXISTS embedding_model TEXT NOT NULL DEFAULT '';
ALTER TABLE doctrine_chunks_v2 ADD COLUMN IF NOT EXISTS embedding_model_version TEXT NOT NULL DEFAULT '';
ALTER TABLE doctrine_chunks_v2 ADD COLUMN IF NOT EXISTS embedding_dimension INTEGER NOT NULL DEFAULT 0;
ALTER TABLE doctrine_chunks_v2 ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE doctrine_chunks_v2 ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'doctrine_chunks_v2_embedding_dimension_check'
          AND conrelid = 'doctrine_chunks_v2'::regclass
    ) THEN
        ALTER TABLE doctrine_chunks_v2
            ADD CONSTRAINT doctrine_chunks_v2_embedding_dimension_check
            CHECK (embedding_dimension >= 0);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_doctrine_chunks_document
    ON doctrine_chunks_v2(document_id, chunk_index);

INSERT INTO doctrine_schema_migrations(migration_id, application_version, notes)
VALUES ('doctrine_phase9_schema_v1', '40.9.10', 'Schema alignment only; no data migration')
ON CONFLICT (migration_id) DO NOTHING;

COMMIT;

-- Rollback policy:
-- 1. Stop the candidate feature flag and retain SQLite fallback.
-- 2. Restore the PostgreSQL backup if a migration transaction must be reverted.
-- 3. Do not DROP populated Doctrine tables or columns automatically.
