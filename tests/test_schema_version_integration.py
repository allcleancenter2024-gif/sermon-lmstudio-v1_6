import os

import pytest

from app.db_adapter import create_database_adapter
from app.schema_version import latest_schema_version, record_schema_version


pytestmark = pytest.mark.integration


def test_restored_database_records_version_and_reconnects():
    if os.environ.get("RUN_SCHEMA_RESTORE_INTEGRATION") != "1":
        pytest.skip("명시적 restore schema 통합시험 플래그가 없어 건너뜁니다.")
    url = os.environ.get("RESTORED_DATABASE_URL", "")
    if "sermon_db_restore_test" not in url or "sermon_db" in url.replace("sermon_db_restore_test", ""):
        pytest.fail("restore 통합시험은 sermon_db_restore_test로 제한됩니다.")
    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    recorded = record_schema_version(adapter, 1, "postgres_restore_verified_v1")
    assert recorded["version"] == 1
    reopened = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    assert latest_schema_version(reopened)["migration_id"] == "postgres_restore_verified_v1"
