import json
import os
from pathlib import Path

import pytest

from app.db_adapter import create_database_adapter
from app.schema_drift_audit import audit_schema


pytestmark = pytest.mark.integration


def test_restore_schema_passes_read_only_manifest_audit():
    if os.environ.get("RUN_SCHEMA_DRIFT_AUDIT") != "1":
        pytest.skip("명시적 schema drift audit 플래그가 없어 건너뜁니다.")
    url = os.environ.get("RESTORED_DATABASE_URL", "")
    if "sermon_db_restore_test" not in url or "sermon_db" in url.replace("sermon_db_restore_test", ""):
        pytest.fail("drift audit는 sermon_db_restore_test로 제한됩니다.")
    manifest = json.loads(Path("scripts/postgres_schema_manifest.json").read_text(encoding="utf-8"))
    adapter = create_database_adapter(environ={"DB_BACKEND": "postgres", "DATABASE_URL": url})
    result = audit_schema(adapter, manifest)
    assert result["status"] == "PASS"
    assert result["missing_tables"] == []
    assert result["missing_extensions"] == []
    assert result["version_match"] is True
