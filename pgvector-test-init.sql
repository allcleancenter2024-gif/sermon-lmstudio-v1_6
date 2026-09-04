CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_embedding_probe (
    id TEXT PRIMARY KEY,
    embedding vector(3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_rag_embedding_probe_cosine
    ON rag_embedding_probe USING hnsw (embedding vector_cosine_ops);
