import pytest

from app.doctrine_backend import create_doctrine_backend


def test_doctrine_backend_defaults_to_existing_sqlite(tmp_path):
    backend = create_doctrine_backend(database_path=tmp_path / "doctrine.sqlite3", environ={})
    assert backend.name == "existing"
    assert backend.repository.adapter is backend.adapter


def test_doctrine_backend_requires_explicit_postgres_url():
    with pytest.raises(ValueError):
        create_doctrine_backend(environ={"DB_BACKEND": "postgres"})
