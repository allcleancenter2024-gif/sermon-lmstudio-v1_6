from app.readiness_audit import audit_test_readiness


class _Row(dict):
    pass


class _Connection:
    def execute(self, sql):
        if "current_database" in sql:
            return type("Cursor", (), {"fetchone": lambda self: _Row(database_name="demo_test", user_name="tester")})()
        raise AssertionError("schema audit query는 이 순수 단위 테스트에서 호출하지 않음")


class _Adapter:
    backend = "postgres"
    def transaction(self):
        class Context:
            def __enter__(self): return _Connection()
            def __exit__(self, *_): return False
        return Context()


def test_readiness_requires_test_only_configuration(monkeypatch):
    monkeypatch.setattr("app.readiness_audit.audit_schema", lambda *_: {"status": "PASS"})
    result = audit_test_readiness(
        _Adapter(), {"required_tables": [], "required_extensions": []},
        minio_config={"endpoint": "http://127.0.0.1:9000", "bucket": "sermon-documents-test",
                      "test_prefix": "_verification/", "access_key": "test", "secret_key": "hidden"},
    )
    assert result["status"] == "PASS"
    assert result["checks"]["database_is_test"] is True


def test_readiness_rejects_production_like_values(monkeypatch):
    monkeypatch.setattr("app.readiness_audit.audit_schema", lambda *_: {"status": "PASS"})
    result = audit_test_readiness(
        _Adapter(), {"required_tables": [], "required_extensions": []},
        minio_config={"endpoint": "http://10.0.0.4:9000", "bucket": "sermon-documents",
                      "test_prefix": "production/", "access_key": "test", "secret_key": "hidden"},
    )
    assert result["status"] == "NOT_READY"
