import pytest

from app.schema_drift_audit import audit_schema


class _Row(dict):
    pass


class _Cursor:
    def __init__(self, rows): self.rows = rows
    def fetchall(self): return self.rows
    def fetchone(self): return self.rows[0] if self.rows else None


class _Connection:
    def execute(self, sql):
        if "information_schema.tables" in sql:
            return _Cursor([_Row(table_name=name) for name in (
                "denominations", "doctrine_sources", "doctrine_documents", "source_snapshots",
                "ingestion_jobs", "object_storage_records", "schema_versions")])
        if "pg_extension" in sql:
            return _Cursor([_Row(extname="vector")])
        return _Cursor([_Row(version=1, migration_id="test_v1")])


class _Adapter:
    backend = "postgres"
    def transaction(self):
        class _Context:
            def __enter__(self): return _Connection()
            def __exit__(self, *_): return False
        return _Context()


def test_schema_drift_audit_is_read_only_and_reports_version_mismatch():
    manifest = {"version": 1, "migration_id": "expected_v1",
                "required_tables": ["schema_versions"], "required_extensions": ["vector"]}
    result = audit_schema(_Adapter(), manifest)
    assert result["status"] == "DRIFT"
    assert result["missing_tables"] == []
    assert result["missing_extensions"] == []
    assert result["version_match"] is False


def test_schema_drift_audit_rejects_non_postgres_adapter():
    with pytest.raises(ValueError):
        audit_schema(type("SQLite", (), {"backend": "existing"})(), {})
