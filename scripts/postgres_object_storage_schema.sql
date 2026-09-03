-- Test-only object storage record schema. Apply to sermon_db_test first.
CREATE TABLE IF NOT EXISTS object_storage_records (
    id UUID PRIMARY KEY,
    document_id BIGINT REFERENCES doctrine_documents(id),
    bucket_name VARCHAR(255) NOT NULL,
    object_key TEXT NOT NULL,
    version_id TEXT,
    sha256 CHAR(64) NOT NULL CHECK (sha256 ~ '^[0-9a-fA-F]{64}$'),
    content_type VARCHAR(255),
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    original_filename TEXT,
    upload_status VARCHAR(30) NOT NULL CHECK (upload_status IN ('PENDING', 'UPLOADED', 'VERIFIED', 'FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at TIMESTAMPTZ,
    UNIQUE (bucket_name, object_key, version_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_object_storage_records_versioned
    ON object_storage_records(bucket_name, object_key, version_id) NULLS NOT DISTINCT;
