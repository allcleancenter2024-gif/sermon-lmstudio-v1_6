"""Small, additive SQLite migrations for denomination doctrine RAG.

The migration deliberately does not alter legacy doctrine or Bible RAG tables.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


MIGRATION_ID = "denomination_doctrine_v1"
ADMIN_MIGRATION_ID = "denomination_doctrine_admin_v1"
OSHB_DEDUPLICATION_ID = "oshb_original_dedup_v1"
LICENSE_REVIEW_MIGRATION_ID = "doctrine_source_license_review_v1"
PHASE1_DATA_MODEL_MIGRATION_ID = "doctrine_phase1_data_model_v2"
PHASE2_INGESTION_MIGRATION_ID = "doctrine_phase2_secure_ingestion_v1"
TABLES = (
    "doctrine_embeddings_v2", "doctrine_chunks_v2", "doctrine_index_versions",
    "ingestion_jobs", "source_snapshots", "doctrine_documents",
    "doctrine_sources", "denominations",
)


def apply_migrations(db_path: Path) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        if con.execute("SELECT 1 FROM schema_migrations WHERE migration_id=?", (MIGRATION_ID,)).fetchone():
            return {"migration_id": MIGRATION_ID, "applied": False}
        con.executescript(
            """
            CREATE TABLE denominations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name_ko TEXT NOT NULL,
                name_en TEXT NOT NULL DEFAULT '',
                tradition TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT '',
                official_site TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE doctrine_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                denomination_id INTEGER NOT NULL REFERENCES denominations(id),
                title TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL,
                source_authority TEXT NOT NULL,
                collection_method TEXT NOT NULL DEFAULT '',
                update_schedule TEXT NOT NULL DEFAULT '',
                license_status TEXT NOT NULL DEFAULT 'UNKNOWN',
                requires_review INTEGER NOT NULL DEFAULT 1 CHECK(requires_review IN (0, 1)),
                active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE doctrine_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES doctrine_sources(id),
                title TEXT NOT NULL,
                adoption_year INTEGER,
                edition TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'ko',
                official_status TEXT NOT NULL DEFAULT 'UNKNOWN',
                published_at TEXT,
                retrieved_at TEXT,
                content_hash TEXT NOT NULL,
                object_storage_key TEXT NOT NULL DEFAULT '',
                mime_type TEXT NOT NULL DEFAULT '',
                review_status TEXT NOT NULL DEFAULT 'DISCOVERED',
                supersedes_document_id INTEGER REFERENCES doctrine_documents(id),
                metadata_json TEXT NOT NULL DEFAULT '{}',
                active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1)),
                created_at TEXT NOT NULL,
                UNIQUE(source_id, content_hash)
            );
            CREATE TABLE source_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES doctrine_sources(id),
                document_id INTEGER REFERENCES doctrine_documents(id),
                checked_at TEXT NOT NULL,
                http_status INTEGER,
                etag TEXT NOT NULL DEFAULT '',
                last_modified TEXT NOT NULL DEFAULT '',
                content_hash TEXT NOT NULL DEFAULT '',
                object_storage_key TEXT NOT NULL DEFAULT '',
                changed INTEGER NOT NULL DEFAULT 0 CHECK(changed IN (0, 1)),
                error_code TEXT NOT NULL DEFAULT '',
                error_summary TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE ingestion_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL REFERENCES doctrine_sources(id),
                document_id INTEGER REFERENCES doctrine_documents(id),
                status TEXT NOT NULL DEFAULT 'DISCOVERED',
                attempts INTEGER NOT NULL DEFAULT 0,
                error_code TEXT NOT NULL DEFAULT '',
                error_summary TEXT NOT NULL DEFAULT '',
                started_at TEXT,
                finished_at TEXT,
                retry_of_job_id INTEGER REFERENCES ingestion_jobs(id)
            );
            CREATE TABLE doctrine_chunks_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL REFERENCES doctrine_documents(id),
                section_path TEXT NOT NULL DEFAULT '',
                article_number TEXT NOT NULL DEFAULT '',
                article_title TEXT NOT NULL DEFAULT '',
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                token_count INTEGER NOT NULL DEFAULT 0,
                scripture_refs TEXT NOT NULL DEFAULT '[]',
                topic_tags TEXT NOT NULL DEFAULT '[]',
                content_hash TEXT NOT NULL,
                UNIQUE(document_id, chunk_index),
                UNIQUE(document_id, content_hash)
            );
            CREATE TABLE doctrine_index_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                model_version TEXT NOT NULL DEFAULT '',
                dimension INTEGER NOT NULL,
                distance_metric TEXT NOT NULL DEFAULT 'cosine',
                status TEXT NOT NULL DEFAULT 'BUILDING',
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE doctrine_embeddings_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL REFERENCES doctrine_chunks_v2(id),
                index_version_id INTEGER NOT NULL REFERENCES doctrine_index_versions(id),
                vector_blob BLOB NOT NULL,
                dimension INTEGER NOT NULL,
                norm REAL NOT NULL,
                UNIQUE(chunk_id, index_version_id)
            );
            CREATE INDEX idx_doctrine_sources_denomination ON doctrine_sources(denomination_id);
            CREATE INDEX idx_doctrine_documents_source_review ON doctrine_documents(source_id, review_status, active);
            CREATE INDEX idx_doctrine_documents_status ON doctrine_documents(official_status, language);
            CREATE INDEX idx_source_snapshots_source_checked ON source_snapshots(source_id, checked_at);
            CREATE INDEX idx_ingestion_jobs_status ON ingestion_jobs(status, source_id);
            CREATE INDEX idx_doctrine_chunks_document ON doctrine_chunks_v2(document_id, chunk_index);
            CREATE INDEX idx_doctrine_embeddings_version ON doctrine_embeddings_v2(index_version_id);
            """
        )
        con.execute(
            "INSERT INTO schema_migrations(migration_id, applied_at) VALUES(?, datetime('now'))",
            (MIGRATION_ID,),
        )
    return {"migration_id": MIGRATION_ID, "applied": True}


def rollback_migration(db_path: Path) -> dict:
    """Rollback only an unused Phase 1 schema; never delete populated data."""
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("PRAGMA foreign_keys=ON")
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone():
            return {"rolled_back": False, "reason": "migration_not_applied"}
        for table in TABLES:
            if con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
                raise RuntimeError("사용 중인 교단 교리 Phase 1 데이터는 자동 삭제 롤백하지 않습니다. 백업 복원을 사용하세요.")
        for table in TABLES:
            con.execute(f"DROP TABLE IF EXISTS {table}")
        con.execute("DELETE FROM schema_migrations WHERE migration_id=?", (MIGRATION_ID,))
    return {"rolled_back": True, "migration_id": MIGRATION_ID}


def apply_admin_workflow_migration(db_path: Path) -> dict:
    """Add review/audit columns without replacing the Phase 1 tables."""
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        if con.execute("SELECT 1 FROM schema_migrations WHERE migration_id=?", (ADMIN_MIGRATION_ID,)).fetchone():
            return {"migration_id": ADMIN_MIGRATION_ID, "applied": False}
        columns = {row[1] for row in con.execute("PRAGMA table_info(doctrine_documents)")}
        for name, definition in {
            "reviewed_by": "TEXT NOT NULL DEFAULT ''",
            "reviewed_at": "TEXT",
            "review_comment": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if name not in columns:
                con.execute(f"ALTER TABLE doctrine_documents ADD COLUMN {name} {definition}")
        con.execute("""CREATE TABLE IF NOT EXISTS doctrine_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL,
            actor TEXT NOT NULL, action TEXT NOT NULL, from_status TEXT NOT NULL,
            to_status TEXT NOT NULL, comment TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        )""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_doctrine_audit_document ON doctrine_audit_log(document_id, created_at)")
        con.execute("INSERT INTO schema_migrations(migration_id, applied_at) VALUES(?, datetime('now'))", (ADMIN_MIGRATION_ID,))
    return {"migration_id": ADMIN_MIGRATION_ID, "applied": True}


def deduplicate_oshb_originals(db_path: Path) -> dict:
    """Keep the earliest OSHB logical row and remove only duplicate imports.

    This is intentionally a manual, idempotent data migration.  It does not
    merge unlike morphology or pronunciation values and does not touch
    non-OSHB sources.  The earliest row is the pre-existing canonical record.
    """
    oshb = "(lower(source) LIKE '%oshb%' OR lower(source) LIKE '%open scriptures%')"
    with closing(sqlite3.connect(db_path)) as con, con:
        note_duplicates = con.execute(f"""
            SELECT COUNT(*) FROM original_word_notes AS newer
            WHERE {oshb} AND EXISTS (
                SELECT 1 FROM original_word_notes AS older
                WHERE {oshb.replace('source', 'older.source')}
                  AND older.id < newer.id
                  AND older.reference = newer.reference
                  AND older.language = newer.language
                  AND older.lemma = newer.lemma
                  AND older.morphology = newer.morphology
            )
        """).fetchone()[0]
        pronunciation_duplicates = con.execute(f"""
            SELECT COUNT(*) FROM original_pronunciations AS newer
            WHERE {oshb} AND EXISTS (
                SELECT 1 FROM original_pronunciations AS older
                WHERE {oshb.replace('source', 'older.source')}
                  AND older.id < newer.id
                  AND older.reference = newer.reference
                  AND older.language = newer.language
                  AND older.lemma = newer.lemma
                  AND older.surface_form = newer.surface_form
                  AND older.token_index = newer.token_index
                  AND older.transliteration = newer.transliteration
                  AND older.pronunciation_scheme = newer.pronunciation_scheme
            )
        """).fetchone()[0]
        con.execute(f"""
            DELETE FROM original_word_notes AS newer
            WHERE {oshb} AND EXISTS (
                SELECT 1 FROM original_word_notes AS older
                WHERE {oshb.replace('source', 'older.source')}
                  AND older.id < newer.id
                  AND older.reference = newer.reference AND older.language = newer.language
                  AND older.lemma = newer.lemma AND older.morphology = newer.morphology
            )
        """)
        con.execute(f"""
            DELETE FROM original_pronunciations AS newer
            WHERE {oshb} AND EXISTS (
                SELECT 1 FROM original_pronunciations AS older
                WHERE {oshb.replace('source', 'older.source')}
                  AND older.id < newer.id AND older.reference = newer.reference
                  AND older.language = newer.language AND older.lemma = newer.lemma
                  AND older.surface_form = newer.surface_form AND older.token_index = newer.token_index
                  AND older.transliteration = newer.transliteration
                  AND older.pronunciation_scheme = newer.pronunciation_scheme
            )
        """)
    return {"migration_id": OSHB_DEDUPLICATION_ID, "notes_removed": int(note_duplicates), "pronunciations_removed": int(pronunciation_duplicates)}


def apply_license_review_migration(db_path: Path) -> dict:
    """Add auditable license evidence fields to doctrine sources."""
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        if con.execute("SELECT 1 FROM schema_migrations WHERE migration_id=?", (LICENSE_REVIEW_MIGRATION_ID,)).fetchone():
            return {"migration_id": LICENSE_REVIEW_MIGRATION_ID, "applied": False}
        columns = {row[1] for row in con.execute("PRAGMA table_info(doctrine_sources)")}
        for name, definition in {
            "permission_ref": "TEXT NOT NULL DEFAULT ''",
            "license_reviewed_by": "TEXT NOT NULL DEFAULT ''",
            "license_reviewed_at": "TEXT",
            "license_review_note": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if name not in columns:
                con.execute(f"ALTER TABLE doctrine_sources ADD COLUMN {name} {definition}")
        con.execute("INSERT INTO schema_migrations(migration_id, applied_at) VALUES(?, datetime('now'))", (LICENSE_REVIEW_MIGRATION_ID,))
    return {"migration_id": LICENSE_REVIEW_MIGRATION_ID, "applied": True}


def apply_phase1_data_model_migration(db_path: Path) -> dict:
    """Add the remaining Phase 1 metadata and database-level guards."""
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        if con.execute("SELECT 1 FROM schema_migrations WHERE migration_id=?", (PHASE1_DATA_MODEL_MIGRATION_ID,)).fetchone():
            return {"migration_id": PHASE1_DATA_MODEL_MIGRATION_ID, "applied": False}
        source_columns = {row[1] for row in con.execute("PRAGMA table_info(doctrine_sources)")}
        if "last_checked_at" not in source_columns:
            con.execute("ALTER TABLE doctrine_sources ADD COLUMN last_checked_at TEXT")
        chunk_columns = {row[1] for row in con.execute("PRAGMA table_info(doctrine_chunks_v2)")}
        for name, definition in {
            "embedding_model": "TEXT NOT NULL DEFAULT ''",
            "embedding_model_version": "TEXT NOT NULL DEFAULT ''",
            "embedding_dimension": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT NOT NULL DEFAULT ''",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        }.items():
            if name not in chunk_columns:
                con.execute(f"ALTER TABLE doctrine_chunks_v2 ADD COLUMN {name} {definition}")
        job_columns = {row[1] for row in con.execute("PRAGMA table_info(ingestion_jobs)")}
        for name, definition in {
            "job_type": "TEXT NOT NULL DEFAULT 'INGEST'",
            "idempotency_key": "TEXT NOT NULL DEFAULT ''",
            "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
            "next_retry_at": "TEXT",
        }.items():
            if name not in job_columns:
                con.execute(f"ALTER TABLE ingestion_jobs ADD COLUMN {name} {definition}")
        con.executescript("""
            CREATE TRIGGER IF NOT EXISTS trg_doctrine_source_license_active
            BEFORE INSERT ON doctrine_sources
            WHEN NEW.active=1 AND NEW.license_status NOT IN ('VERIFIED','PUBLIC_DOMAIN')
            BEGIN SELECT RAISE(ABORT, '라이선스 확인 전 자료원은 활성화할 수 없습니다.'); END;
            CREATE TRIGGER IF NOT EXISTS trg_doctrine_source_license_update
            BEFORE UPDATE OF active, license_status ON doctrine_sources
            WHEN NEW.active=1 AND NEW.license_status NOT IN ('VERIFIED','PUBLIC_DOMAIN')
            BEGIN SELECT RAISE(ABORT, '라이선스 확인 전 자료원은 활성화할 수 없습니다.'); END;
            CREATE TRIGGER IF NOT EXISTS trg_doctrine_document_hash
            BEFORE INSERT ON doctrine_documents
            WHEN length(NEW.content_hash) <> 64 OR NEW.content_hash GLOB '*[^0-9a-fA-F]*'
            BEGIN SELECT RAISE(ABORT, '문서 content_hash는 SHA-256 64자리 hex여야 합니다.'); END;
            CREATE TRIGGER IF NOT EXISTS trg_doctrine_document_supersedes_self
            BEFORE INSERT ON doctrine_documents
            WHEN NEW.supersedes_document_id IS NOT NULL AND NEW.supersedes_document_id=NEW.id
            BEGIN SELECT RAISE(ABORT, '문서는 자기 자신을 이전 판본으로 지정할 수 없습니다.'); END;
            CREATE TRIGGER IF NOT EXISTS trg_doctrine_chunk_values
            BEFORE INSERT ON doctrine_chunks_v2
            WHEN trim(NEW.content)='' OR NEW.chunk_index<0 OR NEW.token_count<0 OR NEW.embedding_dimension<0
            BEGIN SELECT RAISE(ABORT, '교리 청크 값이 유효하지 않습니다.'); END;
            CREATE TRIGGER IF NOT EXISTS trg_ingestion_job_values
            BEFORE INSERT ON ingestion_jobs
            WHEN NEW.attempts<0 OR trim(NEW.job_type)='' OR NEW.metadata_json=''
            BEGIN SELECT RAISE(ABORT, '수집 작업 메타데이터가 유효하지 않습니다.'); END;
            CREATE INDEX IF NOT EXISTS idx_doctrine_documents_source_language_status
              ON doctrine_documents(source_id, language, official_status, review_status, active);
            CREATE INDEX IF NOT EXISTS idx_source_snapshots_hash_checked
              ON source_snapshots(source_id, content_hash, checked_at);
            CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_retry
              ON ingestion_jobs(status, next_retry_at);
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ingestion_jobs_active_idempotency
              ON ingestion_jobs(source_id, idempotency_key)
              WHERE idempotency_key<>'' AND status IN ('DISCOVERED','DOWNLOADING','DOWNLOADED','PARSING','PARSED','PROCESSING');
        """)
        con.execute("INSERT INTO schema_migrations(migration_id, applied_at) VALUES(?, datetime('now'))", (PHASE1_DATA_MODEL_MIGRATION_ID,))
    return {"migration_id": PHASE1_DATA_MODEL_MIGRATION_ID, "applied": True}


def rollback_phase1_data_model_migration(db_path: Path) -> dict:
    """Rollback only the additive Phase 1 layer when no dependent data exists."""
    with closing(sqlite3.connect(db_path)) as con, con:
        if not con.execute("SELECT 1 FROM schema_migrations WHERE migration_id=?", (PHASE1_DATA_MODEL_MIGRATION_ID,)).fetchone():
            return {"migration_id": PHASE1_DATA_MODEL_MIGRATION_ID, "rolled_back": False}
        for table in ("doctrine_documents", "doctrine_chunks_v2", "source_snapshots", "ingestion_jobs", "doctrine_sources"):
            if con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]:
                raise RuntimeError("Phase 1 데이터가 존재하여 자동 downgrade할 수 없습니다. 백업 복원을 사용하세요.")
        con.executescript("""
            DROP INDEX IF EXISTS uq_ingestion_jobs_active_idempotency;
            DROP INDEX IF EXISTS idx_ingestion_jobs_retry;
            DROP INDEX IF EXISTS idx_source_snapshots_hash_checked;
            DROP INDEX IF EXISTS idx_doctrine_documents_source_language_status;
            DROP TRIGGER IF EXISTS trg_ingestion_job_values;
            DROP TRIGGER IF EXISTS trg_doctrine_chunk_values;
            DROP TRIGGER IF EXISTS trg_doctrine_document_supersedes_self;
            DROP TRIGGER IF EXISTS trg_doctrine_document_hash;
            DROP TRIGGER IF EXISTS trg_doctrine_source_license_update;
            DROP TRIGGER IF EXISTS trg_doctrine_source_license_active;
        """)
        for table, column in (
            ("ingestion_jobs", "next_retry_at"), ("ingestion_jobs", "metadata_json"),
            ("ingestion_jobs", "idempotency_key"), ("ingestion_jobs", "job_type"),
            ("doctrine_chunks_v2", "updated_at"), ("doctrine_chunks_v2", "created_at"),
            ("doctrine_chunks_v2", "embedding_dimension"), ("doctrine_chunks_v2", "embedding_model_version"),
            ("doctrine_chunks_v2", "embedding_model"), ("doctrine_sources", "last_checked_at"),
        ):
            con.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        con.execute("DELETE FROM schema_migrations WHERE migration_id=?", (PHASE1_DATA_MODEL_MIGRATION_ID,))
    return {"migration_id": PHASE1_DATA_MODEL_MIGRATION_ID, "rolled_back": True}


def apply_phase2_ingestion_migration(db_path: Path) -> dict:
    """Add only provenance and recovery fields required by secure ingestion."""
    with closing(sqlite3.connect(db_path)) as con, con:
        con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        if con.execute("SELECT 1 FROM schema_migrations WHERE migration_id=?", (PHASE2_INGESTION_MIGRATION_ID,)).fetchone():
            return {"migration_id": PHASE2_INGESTION_MIGRATION_ID, "applied": False}
        for table, fields in {
            "source_snapshots": {"request_url": "TEXT NOT NULL DEFAULT ''", "final_url": "TEXT NOT NULL DEFAULT ''", "mime_type": "TEXT NOT NULL DEFAULT ''", "content_length": "INTEGER NOT NULL DEFAULT 0", "sha256_verified": "INTEGER NOT NULL DEFAULT 0", "verification_error": "TEXT NOT NULL DEFAULT ''"},
            "ingestion_jobs": {"http_status": "INTEGER", "retry_after": "INTEGER", "storage_status": "TEXT NOT NULL DEFAULT 'NOT_STARTED'", "storage_key": "TEXT NOT NULL DEFAULT ''", "bytes_received": "INTEGER NOT NULL DEFAULT 0", "error_category": "TEXT NOT NULL DEFAULT ''"},
        }.items():
            columns = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            for name, definition in fields.items():
                if name not in columns:
                    con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        con.execute("CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_storage_status ON ingestion_jobs(storage_status, finished_at)")
        con.execute("INSERT INTO schema_migrations(migration_id, applied_at) VALUES(?, datetime('now'))", (PHASE2_INGESTION_MIGRATION_ID,))
    return {"migration_id": PHASE2_INGESTION_MIGRATION_ID, "applied": True}


def rollback_phase2_ingestion_migration(db_path: Path) -> dict:
    """Remove only unused Phase 2 columns; populated data requires backup restore."""
    with closing(sqlite3.connect(db_path)) as con, con:
        if not con.execute("SELECT 1 FROM schema_migrations WHERE migration_id=?", (PHASE2_INGESTION_MIGRATION_ID,)).fetchone():
            return {"migration_id": PHASE2_INGESTION_MIGRATION_ID, "rolled_back": False}
        if con.execute("SELECT COUNT(*) FROM source_snapshots").fetchone()[0] or con.execute("SELECT COUNT(*) FROM ingestion_jobs").fetchone()[0]:
            raise RuntimeError("Phase 2 수집 이력이 존재하여 자동 downgrade할 수 없습니다. DB 백업 복원을 사용하세요.")
        con.execute("DROP INDEX IF EXISTS idx_ingestion_jobs_storage_status")
        for table, column in (("source_snapshots", "verification_error"), ("source_snapshots", "sha256_verified"), ("source_snapshots", "content_length"), ("source_snapshots", "mime_type"), ("source_snapshots", "final_url"), ("source_snapshots", "request_url"), ("ingestion_jobs", "error_category"), ("ingestion_jobs", "bytes_received"), ("ingestion_jobs", "storage_key"), ("ingestion_jobs", "storage_status"), ("ingestion_jobs", "retry_after"), ("ingestion_jobs", "http_status")):
            con.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        con.execute("DELETE FROM schema_migrations WHERE migration_id=?", (PHASE2_INGESTION_MIGRATION_ID,))
    return {"migration_id": PHASE2_INGESTION_MIGRATION_ID, "rolled_back": True}
