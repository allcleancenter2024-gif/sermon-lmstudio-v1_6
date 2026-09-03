from app.db_adapter import create_database_adapter
from app.schema_version import latest_schema_version, record_schema_version


def test_schema_version_is_idempotent_and_conflicts_are_rejected(tmp_path):
    adapter = create_database_adapter(database_path=tmp_path / "schema.sqlite3", environ={"DB_BACKEND": "existing"})
    first = record_schema_version(adapter, 1, "doctrine_test_v1")
    second = record_schema_version(adapter, 1, "doctrine_test_v1")
    assert first["migration_id"] == second["migration_id"] == "doctrine_test_v1"
    assert latest_schema_version(adapter)["version"] == 1

    try:
        record_schema_version(adapter, 1, "different_migration")
    except ValueError as exc:
        assert "다른 migration_id" in str(exc)
    else:
        raise AssertionError("동일 version의 다른 migration_id가 허용됨")
