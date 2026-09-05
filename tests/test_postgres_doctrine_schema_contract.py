from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_postgres_doctrine_schema_matches_sqlite_processing_contract():
    schema = (ROOT / "scripts" / "postgres_doctrine_chunks_schema.sql").read_text(encoding="utf-8")
    for column in (
        "embedding_model", "embedding_model_version", "embedding_dimension",
        "created_at", "updated_at",
    ):
        assert column in schema
    assert "CHECK (embedding_dimension >= 0)" in schema


def test_phase9_doctrine_migration_is_gated_and_non_destructive():
    migration = (ROOT / "scripts" / "postgres_doctrine_phase9_migration.sql").read_text(encoding="utf-8")
    assert "BEGIN;" in migration and "COMMIT;" in migration
    assert "doctrine_phase9_schema_v1" in migration
    assert "DROP TABLE" not in migration
    assert "DROP COLUMN" not in migration
    assert "no data migration" in migration
