CREATE TABLE IF NOT EXISTS object_storage_records (
    id TEXT PRIMARY KEY,
    document_id BIGINT,
    bucket_name TEXT NOT NULL,
    object_key TEXT NOT NULL,
    version_id TEXT,
    sha256 TEXT NOT NULL,
    content_type TEXT,
    size_bytes BIGINT NOT NULL,
    original_filename TEXT,
    upload_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_object_storage_records_object
    ON object_storage_records(bucket_name, object_key, COALESCE(version_id, ''));
