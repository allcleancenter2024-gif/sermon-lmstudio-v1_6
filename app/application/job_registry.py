"""Thread-safe in-memory registry for active local workflow jobs."""

from threading import Lock

from app.application.job_progress import JobProgress


_JOBS: dict[str, JobProgress] = {}
_LOCK = Lock()


def start_job(job_id: str) -> JobProgress | None:
    key = str(job_id or "").strip()
    if not key:
        return None
    with _LOCK:
        job = JobProgress(key).start()
        _JOBS[key] = job
        return job


def finish_job(job_id: str, message: str = "") -> JobProgress | None:
    with _LOCK:
        job = _JOBS.get(str(job_id or "").strip())
        if not job:
            return None
        if job.status in {"cancelled", "failed"}:
            return job
        job = job.finish(message)
        _JOBS[job.job_id] = job
        return job


def update_job(job_id: str, percent: int, message: str = "") -> JobProgress | None:
    with _LOCK:
        job = _JOBS.get(str(job_id or "").strip())
        if not job:
            return None
        job = job.update(percent, message)
        _JOBS[job.job_id] = job
        return job


def fail_job(job_id: str, message: str = "작업이 실패했습니다.") -> JobProgress | None:
    with _LOCK:
        job = _JOBS.get(str(job_id or "").strip())
        if not job:
            return None
        if job.status in {"completed", "cancelled"}:
            return job
        job = job.stop("failed", message)
        _JOBS[job.job_id] = job
        return job


def cancel_job(job_id: str, message: str = "사용자가 작업을 취소했습니다.") -> JobProgress | None:
    with _LOCK:
        job = _JOBS.get(str(job_id or "").strip())
        if not job:
            return None
        job = job.stop("cancelled", message)
        _JOBS[job.job_id] = job
        return job


def get_job(job_id: str) -> JobProgress | None:
    with _LOCK:
        return _JOBS.get(str(job_id or "").strip())


def clear_jobs() -> None:
    """Test/support hook; does not touch persistent data."""
    with _LOCK:
        _JOBS.clear()
