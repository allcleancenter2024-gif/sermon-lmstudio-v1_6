import pytest

from app.db_adapter import DatabaseConstraintError, create_database_adapter
from app.doctrine_repository_contract import DoctrineRepository


def test_timestamp_json_and_constraint_contract_on_sqlite(tmp_path):
    adapter = create_database_adapter(database_path=tmp_path / "constraints.sqlite3", environ={"DB_BACKEND": "existing"})
    with adapter.transaction() as con:
        repo = DoctrineRepository(adapter)
        repo.ensure_sqlite_tables(con)
        repo.create_fixture(con)
        document_id = con.execute("SELECT id FROM doctrine_documents WHERE object_storage_key=?", ("_verification/adapter-compare.txt",)).fetchone()[0]
        repo.set_document_metadata(con, document_id, {"source": "fixture", "verified": True})
        assert repo.get_document_metadata(con, document_id) == {"source": "fixture", "verified": True}
        with pytest.raises(DatabaseConstraintError) as duplicate:
            repo.create_fixture(con)
        assert duplicate.value.kind == "unique"
        with pytest.raises(DatabaseConstraintError) as foreign_key:
            repo.insert_invalid_source(con)
        assert foreign_key.value.kind == "foreign_key"
        created_at = con.execute("SELECT created_at FROM doctrine_documents WHERE id=?", (document_id,)).fetchone()[0]
        assert created_at
