"""Small doctrine repository contract used for SQLite/PostgreSQL comparison."""

from __future__ import annotations

import json

from app.db_adapter import translate_database_error


class DoctrineRepository:
    def __init__(self, adapter):
        self.adapter = adapter
        self.placeholder = "?" if adapter.backend == "existing" else "%s"

    def ensure_sqlite_tables(self, con) -> None:
        if self.adapter.backend != "existing":
            return
        con.executescript("""
            CREATE TABLE IF NOT EXISTS denominations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE,
                name_ko TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS doctrine_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT, denomination_id INTEGER NOT NULL REFERENCES denominations(id),
                title TEXT NOT NULL, source_url TEXT NOT NULL, source_authority TEXT NOT NULL,
                license_status TEXT NOT NULL DEFAULT 'UNKNOWN', active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS doctrine_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL REFERENCES doctrine_sources(id),
                title TEXT NOT NULL, language TEXT NOT NULL DEFAULT 'ko',
                content_hash TEXT NOT NULL, object_storage_key TEXT NOT NULL DEFAULT '',
                mime_type TEXT NOT NULL DEFAULT '', metadata_json TEXT NOT NULL DEFAULT '{}', active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS doctrine_chunks_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL REFERENCES doctrine_documents(id),
                section_path TEXT NOT NULL DEFAULT '', article_number TEXT NOT NULL DEFAULT '', article_title TEXT NOT NULL DEFAULT '',
                chunk_index INTEGER NOT NULL, content TEXT NOT NULL, token_count INTEGER NOT NULL DEFAULT 0,
                scripture_refs TEXT NOT NULL DEFAULT '[]', topic_tags TEXT NOT NULL DEFAULT '[]', content_hash TEXT NOT NULL,
                UNIQUE(document_id, chunk_index), UNIQUE(document_id, content_hash)
            );
        """)

    def create_fixture(self, con) -> dict:
        p = self.placeholder
        row = self._execute(con,
            f"INSERT INTO denominations(code,name_ko,active,created_at,updated_at) "
            f"VALUES({p},{p},TRUE,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) RETURNING id",
            ("ADAPTER_COMPARE", "Adapter 비교 교단"),
        ).fetchone()
        denomination_id = row["id"] if isinstance(row, dict) else row[0]
        row = self._execute(con,
            f"INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,license_status,active,created_at,updated_at) "
            f"VALUES({p},{p},{p},{p},{p},FALSE,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP) RETURNING id",
            (denomination_id, "Adapter 비교 출처", "https://example.invalid/fixture", "TEST_FIXTURE", "UNKNOWN"),
        ).fetchone()
        source_id = row["id"] if isinstance(row, dict) else row[0]
        row = self._execute(con,
            f"INSERT INTO doctrine_documents(source_id,title,language,content_hash,object_storage_key,mime_type,active,created_at) "
            f"VALUES({p},{p},{p},{p},{p},{p},FALSE,CURRENT_TIMESTAMP) RETURNING id",
            (source_id, "Adapter 비교 문서", "ko", "c" * 64, "_verification/adapter-compare.txt", "text/plain"),
        ).fetchone()
        document_id = row["id"] if isinstance(row, dict) else row[0]
        return {"denomination": self._fetch_one(con, "denominations", denomination_id),
                "source": self._fetch_one(con, "doctrine_sources", source_id),
                "document": self._fetch_one(con, "doctrine_documents", document_id)}

    def set_document_metadata(self, con, document_id: int, metadata: dict) -> None:
        value = json.dumps(metadata, ensure_ascii=False) if self.adapter.backend == "existing" else __import__("psycopg.types.json", fromlist=["Json"]).Json(metadata)
        self._execute(con, f"UPDATE doctrine_documents SET metadata_json={self.placeholder} WHERE id={self.placeholder}",
                      (value, document_id))

    def get_document_for_processing(self, con, document_id: int) -> dict:
        cursor = con.execute(
            f"SELECT id, object_storage_key, mime_type, review_status, active FROM doctrine_documents WHERE id={self.placeholder}",
            (int(document_id),),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("처리할 교리 문서를 찾지 못했습니다.")
        return dict(row) if isinstance(row, dict) else dict(zip([d[0] for d in cursor.description], row))

    def update_review_state(self, con, document_id: int, review_status: str, active: bool = False) -> None:
        self._execute(con,
                      f"UPDATE doctrine_documents SET review_status={self.placeholder}, active={self.placeholder} WHERE id={self.placeholder}",
                      (review_status, active, int(document_id)))

    def get_document_metadata(self, con, document_id: int) -> dict:
        cursor = con.execute(f"SELECT metadata_json FROM doctrine_documents WHERE id={self.placeholder}", (document_id,))
        row = cursor.fetchone()
        value = row["metadata_json"] if isinstance(row, dict) else row[0]
        return json.loads(value) if isinstance(value, str) else dict(value or {})

    def insert_invalid_source(self, con) -> None:
        self._execute(con, f"INSERT INTO doctrine_sources(denomination_id,title,source_url,source_authority,created_at,updated_at) VALUES({self.placeholder},{self.placeholder},{self.placeholder},{self.placeholder},CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
                      (999999999, "invalid", "https://example.invalid", "TEST"))

    def _execute(self, con, sql: str, params=()):
        try:
            return con.execute(sql, params)
        except Exception as exc:
            translated = translate_database_error(exc)
            if translated: raise translated from exc
            raise

    def _fetch_one(self, con, table: str, record_id) -> dict:
        p = self.placeholder
        cursor = con.execute(f"SELECT * FROM {table} WHERE id={p}", (record_id,))
        row = cursor.fetchone()
        data = dict(row) if isinstance(row, dict) else dict(zip([d[0] for d in cursor.description], row))
        return {key: data[key] for key in ("code", "name_ko", "title", "source_url", "source_authority",
                                            "license_status", "content_hash", "object_storage_key", "mime_type") if key in data}


class DoctrineChunkRepository:
    """Backend-neutral replace/read contract for processed doctrine chunks."""

    def __init__(self, adapter):
        self.adapter = adapter
        self.placeholder = "?" if adapter.backend == "existing" else "%s"

    def replace_chunks(self, con, document_id: int, chunks: list[dict]) -> int:
        p = self.placeholder
        con.execute(f"DELETE FROM doctrine_chunks_v2 WHERE document_id={p}", (int(document_id),))
        values = []
        for chunk in chunks:
            refs = json.dumps(chunk.get("scripture_refs", []), ensure_ascii=False)
            tags = json.dumps(chunk.get("topic_tags", []), ensure_ascii=False)
            if self.adapter.backend == "postgres":
                refs = __import__("psycopg.types.json", fromlist=["Json"]).Json(chunk.get("scripture_refs", []))
                tags = __import__("psycopg.types.json", fromlist=["Json"]).Json(chunk.get("topic_tags", []))
            values.append((int(document_id), str(chunk.get("section_path", "")), str(chunk.get("article_number", "")),
                           str(chunk.get("article_title", "")), int(chunk["chunk_index"]), str(chunk["content"]),
                           int(chunk.get("token_count", 0)), refs, tags, str(chunk["content_hash"])))
        if values:
            cursor = con.cursor()
            cursor.executemany(
                f"INSERT INTO doctrine_chunks_v2(document_id,section_path,article_number,article_title,chunk_index,content,token_count,scripture_refs,topic_tags,content_hash) VALUES({','.join([p] * 10)})",
                values,
            )
        return len(values)

    def list_chunks(self, con, document_id: int) -> list[dict]:
        p = self.placeholder
        cursor = con.execute(
            f"SELECT document_id, section_path, article_number, article_title, chunk_index, content, token_count, scripture_refs, topic_tags, content_hash FROM doctrine_chunks_v2 WHERE document_id={p} ORDER BY chunk_index",
            (int(document_id),),
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            data = dict(row) if isinstance(row, dict) else dict(zip([d[0] for d in cursor.description], row))
            for key in ("scripture_refs", "topic_tags"):
                if isinstance(data[key], str): data[key] = json.loads(data[key])
            result.append(data)
        return result
