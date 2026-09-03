import os
import sqlite3

import pytest

from app.db_adapter import create_database_adapter
from app.doctrine_repository_contract import DoctrineRepository
from tests.test_doctrine_repository_contract import _Rollback, _run_fixture


pytestmark = pytest.mark.integration


def test_same_doctrine_fixture_matches_postgres_and_sqlite():
    if os.environ.get("RUN_DOCTRINE_COMPARE") != "1":
        pytest.skip("명시적 doctrine adapter 비교 플래그가 없어 건너뜁니다.")
    url = os.environ.get("RESTORED_DATABASE_URL", "")
    if "sermon_db_restore_test_v2" not in url or "sermon_db" in url.replace("sermon_db_restore_test_v2", ""):
        pytest.fail("비교시험은 sermon_db_restore_test_v2로 제한됩니다.")
    sqlite_adapter = create_database_adapter(database_path=":memory:", environ={"DB_BACKEND": "existing"})
    sqlite_result = _run_fixture(sqlite_adapter)
    postgres_adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    try:
        with postgres_adapter.transaction() as con:
            postgres_result = DoctrineRepository(postgres_adapter).create_fixture(con)
            raise _Rollback(postgres_result)
    except _Rollback as exc:
        postgres_result = exc.value
    assert postgres_result == sqlite_result
