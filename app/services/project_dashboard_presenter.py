"""Pure response composition for the project dashboard.

The presenter deliberately knows nothing about SQLite, FastAPI, or ``app.core``.
Repository input, review-state loading, and duration estimation are injected so
the dashboard response contract can be tested without a database.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


DashboardInput = dict[str, Any]
ReviewStateLoader = Callable[[int, int, Path], dict[str, Any]]
MinutesEstimator = Callable[[str, int], float]


def compose_project_dashboard(
    dashboard_inputs: Sequence[DashboardInput],
    db_path: Path,
    *,
    load_review_state: ReviewStateLoader,
    estimate_minutes: MinutesEstimator,
    reading_cpm: int,
) -> dict[str, Any]:
    """Compose the stable project-dashboard response from prepared inputs."""
    projects = []
    for dashboard_input in dashboard_inputs:
        sermon = dashboard_input["sermon"]
        sermon_id = int(sermon["id"])
        version = dashboard_input["version"]
        version_item = dashboard_input["version_item"]
        meta = version_item.get("metadata") or {}
        state = load_review_state(sermon_id, version, db_path)
        audit = state.get("audit") or {}
        item_reading_cpm = int(meta.get("reading_cpm") or 330)
        project = dashboard_input["project"]
        projects.append({
            "sermon_id": sermon_id, "topic": sermon["topic"], "latest_version": version,
            "service_date": project["service_date"], "series_name": project["series_name"], "preacher": project["preacher"],
            "notes": project["notes"], "state": state["state"], "audit_status": audit.get("status", "none"),
            "locked": state["locked"], "target_minutes": int(meta.get("target_minutes") or meta.get("minutes") or 20),
            "minutes_estimate": estimate_minutes(version_item["content"], item_reading_cpm),
            "reading_cpm": item_reading_cpm, "updated_at": version_item["created_at"],
        })
    counts = {
        status: sum(1 for project in projects if project["state"] == status)
        for status in ("unreviewed", "comment", "changes_requested", "approved", "locked")
    }
    return {"projects": projects, "summary": {"total": len(projects), **counts}, "reading_cpm": reading_cpm}
