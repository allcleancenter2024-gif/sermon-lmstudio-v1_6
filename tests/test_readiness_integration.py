import json
import os
from pathlib import Path

import pytest

from app.db_adapter import create_database_adapter
from app.doctrine_storage import MinioObjectStore
from app.readiness_audit import audit_test_readiness


pytestmark = pytest.mark.integration


def test_isolated_readiness_audit_passes_without_writes():
    if os.environ.get("RUN_READINESS_AUDIT") != "1":
        pytest.skip("명시적 readiness audit 플래그가 없어 건너뜁니다.")
    database_url = os.environ.get("RESTORED_DATABASE_URL", "")
    if "sermon_db_restore_test_v2" not in database_url or "sermon_db" in database_url.replace("sermon_db_restore_test_v2", ""):
        pytest.fail("readiness audit는 sermon_db_restore_test_v2로 제한됩니다.")
    manifest = json.loads(Path("scripts/postgres_schema_manifest.json").read_text(encoding="utf-8"))
    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": database_url})
    store = MinioObjectStore.from_env()
    result = audit_test_readiness(
        adapter,
        manifest,
        minio_config={"endpoint": os.environ["MINIO_ENDPOINT"], "bucket": os.environ["MINIO_BUCKET"],
                      "test_prefix": os.environ["MINIO_TEST_PREFIX"],
                      "access_key": os.environ["MINIO_ACCESS_KEY"], "secret_key": os.environ["MINIO_SECRET_KEY"]},
        minio_probe=lambda: store.list_keys(os.environ["MINIO_TEST_PREFIX"]),
    )
    assert result["status"] == "PASS"
    assert all(result["checks"].values())
