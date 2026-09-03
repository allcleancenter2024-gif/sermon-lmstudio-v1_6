import sqlite3

from app.db_adapter import create_database_adapter
from app.doctrine_repository_contract import DoctrineRepository


class _Rollback(Exception):
    def __init__(self, value): self.value = value


def _run_fixture(adapter):
    try:
        with adapter.transaction() as con:
            repository = DoctrineRepository(adapter)
            repository.ensure_sqlite_tables(con)
            result = repository.create_fixture(con)
            raise _Rollback(result)
    except _Rollback as exc:
        return exc.value


def test_sqlite_doctrine_fixture_contract_rolls_back(tmp_path):
    adapter = create_database_adapter(database_path=tmp_path / "contract.sqlite3", environ={"DB_BACKEND": "existing"})
    result = _run_fixture(adapter)
    assert result["source"]["source_authority"] == "TEST_FIXTURE"
    with sqlite3.connect(tmp_path / "contract.sqlite3") as con:
        assert con.execute("SELECT COUNT(*) FROM denominations").fetchone()[0] == 0
