"""Small, explicit database adapter boundary for the PostgreSQL dry-run.

The production application continues to use its existing SQLite path.  This
module is intentionally narrow: it provides connection/transaction lifecycle
and object-storage metadata CRUD for the isolated migration rehearsal.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
import sqlite3
from typing import Any, Iterator


class DatabaseConfigurationError(ValueError):
    """Raised when backend configuration is missing or unsafe."""


class DatabaseConstraintError(RuntimeError):
    """Backend-neutral integrity error for repository callers."""

    def __init__(self, kind: str):
        self.kind = kind
        super().__init__(f"데이터베이스 무결성 제약 위반: {kind}")


class DatabaseTransientError(RuntimeError):
    """Retryable database failure without exposing backend details."""

    def __init__(self, kind: str):
        self.kind = kind
        super().__init__(f"데이터베이스 일시 오류: {kind}")


def translate_database_error(exc: Exception) -> DatabaseConstraintError | DatabaseTransientError | None:
    if isinstance(exc, sqlite3.IntegrityError):
        message = str(exc).lower()
        if "unique" in message: return DatabaseConstraintError("unique")
        if "foreign key" in message: return DatabaseConstraintError("foreign_key")
        if "not null" in message: return DatabaseConstraintError("not_null")
        return DatabaseConstraintError("integrity")
    try:
        import psycopg.errors as pg_errors
        if isinstance(exc, pg_errors.UniqueViolation): return DatabaseConstraintError("unique")
        if isinstance(exc, pg_errors.ForeignKeyViolation): return DatabaseConstraintError("foreign_key")
        if isinstance(exc, pg_errors.NotNullViolation): return DatabaseConstraintError("not_null")
        if isinstance(exc, pg_errors.DeadlockDetected): return DatabaseTransientError("deadlock")
        if isinstance(exc, pg_errors.LockNotAvailable): return DatabaseTransientError("lock_timeout")
        if isinstance(exc, pg_errors.QueryCanceled): return DatabaseTransientError("query_timeout")
    except ImportError:  # pragma: no cover
        pass
    return None


@dataclass(frozen=True)
class DatabaseSettings:
    backend: str
    database_url: str = ""

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "DatabaseSettings":
        env = os.environ if environ is None else environ
        backend = env.get("DB_BACKEND", "existing").strip().lower()
        if backend not in {"existing", "postgres"}:
            raise DatabaseConfigurationError("DB_BACKEND는 existing 또는 postgres여야 합니다.")
        url = env.get("DATABASE_URL", "").strip()
        if backend == "postgres" and not url:
            raise DatabaseConfigurationError("postgres backend에는 DATABASE_URL이 필요합니다.")
        return cls(backend=backend, database_url=url)


class SQLiteAdapter:
    backend = "existing"

    def __init__(self, database_path):
        self.database_path = database_path

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.database_path)
        con.row_factory = sqlite3.Row
        try:
            con.execute("PRAGMA foreign_keys=ON")
            with con:
                yield con
        finally:
            con.close()


class PostgresAdapter:
    backend = "postgres"

    def __init__(self, database_url: str):
        if not database_url:
            raise DatabaseConfigurationError("PostgreSQL 연결 문자열이 필요합니다.")
        self.database_url = database_url

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise DatabaseConfigurationError("PostgreSQL 드라이버 psycopg가 설치되지 않았습니다.") from exc
        from psycopg.rows import dict_row
        with psycopg.connect(self.database_url, row_factory=dict_row) as con:
            yield con


def create_database_adapter(*, database_path=None, environ: dict[str, str] | None = None):
    """Select a backend explicitly; never fall back after a PostgreSQL error."""
    settings = DatabaseSettings.from_env(environ)
    if settings.backend == "existing":
        if database_path is None:
            raise DatabaseConfigurationError("existing backend에는 SQLite database_path가 필요합니다.")
        return SQLiteAdapter(database_path)
    return PostgresAdapter(settings.database_url)


class ObjectStorageRecordRepository:
    """Backend-neutral CRUD for the test object metadata table."""

    def __init__(self, adapter):
        self.adapter = adapter

    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        placeholder = "?" if self.adapter.backend == "existing" else "%s"
        columns = ("id", "document_id", "bucket_name", "object_key", "version_id", "sha256",
                   "content_type", "size_bytes", "original_filename", "upload_status")
        values = tuple(record.get(column) for column in columns)
        sql = ("INSERT INTO object_storage_records (" + ", ".join(columns) + ") VALUES (" +
               ", ".join([placeholder] * len(columns)) + ")")
        with self.adapter.transaction() as con:
            try:
                con.execute(sql, values)
            except Exception as exc:
                translated = translate_database_error(exc)
                if translated: raise translated from exc
                raise
        return self.get(record["id"])

    def get(self, record_id: str) -> dict[str, Any] | None:
        placeholder = "?" if self.adapter.backend == "existing" else "%s"
        with self.adapter.transaction() as con:
            row = con.execute(
                f"SELECT id, document_id, bucket_name, object_key, version_id, sha256, content_type, "
                f"size_bytes, original_filename, upload_status FROM object_storage_records WHERE id={placeholder}",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row) if isinstance(row, sqlite3.Row) else dict(row)

    def find_by_object(self, bucket_name: str, object_key: str, version_id: str | None = None) -> dict[str, Any] | None:
        """Find one immutable object reference with NULL-safe version matching."""
        placeholder = "?" if self.adapter.backend == "existing" else "%s"
        version_clause = f"version_id IS NULL" if version_id is None else f"version_id={placeholder}"
        params = (bucket_name, object_key) if version_id is None else (bucket_name, object_key, version_id)
        with self.adapter.transaction() as con:
            row = con.execute(
                f"SELECT id, document_id, bucket_name, object_key, version_id, sha256, content_type, "
                f"size_bytes, original_filename, upload_status FROM object_storage_records "
                f"WHERE bucket_name={placeholder} AND object_key={placeholder} AND {version_clause}",
                params,
            ).fetchone()
        if row is None:
            return None
        return dict(row) if isinstance(row, sqlite3.Row) else dict(row)
