from app.phase_readiness import build_phase_readiness


def test_all_test_components_pass_but_cutover_stays_blocked():
    result = build_phase_readiness(
        test_environment=True,
        component_results={name: True for name in (
            "schema_manifest", "adapter_regression", "transaction_rollback",
            "constraint_contract", "minio_metadata", "failure_handling")},
    )
    assert result["status"] == "PASS"
    assert result["cutover_allowed"] is False
    assert any("cutover" in blocker for blocker in result["blockers"])


def test_missing_or_failed_component_is_not_ready():
    result = build_phase_readiness(test_environment=True, component_results={"schema_manifest": False})
    assert result["status"] == "NOT_READY"
    assert result["cutover_allowed"] is False
    assert "adapter_regression" in result["blockers"][0] or any("누락" in item for item in result["blockers"])
