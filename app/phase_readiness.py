"""Aggregate dry-run results without ever authorizing production cutover."""

from __future__ import annotations


REQUIRED_COMPONENTS = (
    "schema_manifest",
    "adapter_regression",
    "transaction_rollback",
    "constraint_contract",
    "minio_metadata",
    "failure_handling",
)


def build_phase_readiness(*, test_environment: bool, component_results: dict[str, bool]) -> dict:
    """Build a conservative readiness result; production cutover is never implicit."""
    missing = sorted(set(REQUIRED_COMPONENTS) - set(component_results))
    failed = sorted(name for name in REQUIRED_COMPONENTS if component_results.get(name) is False)
    blockers = []
    if not test_environment:
        blockers.append("테스트 환경이 아니므로 readiness audit를 통과시킬 수 없습니다.")
    if missing:
        blockers.append("필수 component 결과가 누락되었습니다: " + ", ".join(missing))
    if failed:
        blockers.append("실패한 component가 있습니다: " + ", ".join(failed))
    blockers.append("운영 PostgreSQL cutover는 이 dry-run 범위에서 자동 승인하지 않습니다.")
    return {
        "status": "PASS" if test_environment and not missing and not failed else "NOT_READY",
        "cutover_allowed": False,
        "required_components": list(REQUIRED_COMPONENTS),
        "component_results": {name: component_results.get(name) for name in REQUIRED_COMPONENTS},
        "blockers": blockers,
    }
