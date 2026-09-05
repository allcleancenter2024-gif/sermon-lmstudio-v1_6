from app.application import sermon_facade


def test_sermon_facade_delegates_to_grounded_generation_service(monkeypatch):
    calls = []

    def fake_workflow(*args, **kwargs):
        calls.append((args, kwargs))
        return {"sermon": "본문", "audit_id": "audit-1"}

    monkeypatch.setattr(sermon_facade.sermon_service, "generate_sermon_workflow", fake_workflow)
    result = sermon_facade.generate_sermon_workflow("request", client="client")

    assert result["audit_id"] == "audit-1"
    assert result["profile_version_id"]["sermon_format"] == "format:expository:v1"
    assert result["profile_snapshot"]["audience"]["code"] == "전 연령"
    assert calls == [(('request',), {"client": "client"})]
