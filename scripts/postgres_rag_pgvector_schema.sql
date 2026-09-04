-- Explicit, isolated pgvector RAG schema.
-- Do not apply to a production database until migration and rollback approval.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS rag_pgvector_passages (
    id BIGINT PRIMARY KEY,
    translation TEXT NOT NULL,
    language TEXT NOT NULL,
    reference TEXT NOT NULL,
    text TEXT NOT NULL,
    license_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS rag_pgvector_embeddings (
    passage_id BIGINT NOT NULL REFERENCES rag_pgvector_passages(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    dimension INTEGER NOT NULL CHECK (dimension = 768),
    embedding vector(768) NOT NULL,
    PRIMARY KEY (passage_id, model)
);

CREATE INDEX IF NOT EXISTS ix_rag_pgvector_embeddings_model_cosine
    ON rag_pgvector_embeddings USING hnsw (embedding vector_cosine_ops);
