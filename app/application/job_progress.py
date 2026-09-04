"""Backend-neutral Job/Progress contract for long-running workflows.

This phase defines state semantics only. Existing browser progress displays and
the ingestion_jobs table remain unchanged until an explicit integration phase.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Literal


JobStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class JobProgress:
    job_id: str
    status: JobStatus = "pending"
    percent: int = 0
    started_at: datetime | None = None
    updated_at: datetime | None = None
    estimated_total_seconds: float | None = None
    message: str = ""

    def start(self, now: datetime | None = None) -> "JobProgress":
        if self.status not in {"pending", "running"}:
            raise ValueError("완료·실패·취소된 작업은 다시 시작할 수 없습니다.")
        current = now or _now()
        return replace(self, status="running", started_at=self.started_at or current, updated_at=current)

    def update(self, percent: int, message: str = "", now: datetime | None = None) -> "JobProgress":
        if self.status not in {"running", "pending"}:
            raise ValueError("실행 중인 작업만 진행률을 갱신할 수 있습니다.")
        if not 0 <= int(percent) <= 100:
            raise ValueError("진행률은 0에서 100 사이여야 합니다.")
        if int(percent) < self.percent:
            raise ValueError("진행률은 이전 값보다 작아질 수 없습니다.")
        current = now or _now()
        if self.started_at is None:
            started = current
        else:
            started = self.started_at
        total = self.estimated_total_seconds
        if total is None and int(percent) > 0:
            elapsed = max(0.0, (current - started).total_seconds())
            total = elapsed * 100 / int(percent)
        return replace(self, status="running", percent=int(percent), started_at=started, updated_at=current, estimated_total_seconds=total, message=message)

    def finish(self, message: str = "", now: datetime | None = None) -> "JobProgress":
        current = now or _now()
        return replace(self, status="completed", percent=100, started_at=self.started_at or current, updated_at=current, message=message)

    def stop(self, status: Literal["failed", "cancelled"], message: str, now: datetime | None = None) -> "JobProgress":
        if status not in {"failed", "cancelled"}:
            raise ValueError("stop 상태는 failed 또는 cancelled만 허용됩니다.")
        return replace(self, status=status, updated_at=now or _now(), message=message)

    def estimated_completion(self) -> datetime | None:
        if not self.started_at or not self.estimated_total_seconds or self.status in {"completed", "failed", "cancelled"}:
            return None
        return self.started_at + timedelta(seconds=self.estimated_total_seconds)
