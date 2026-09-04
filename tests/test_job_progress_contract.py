from datetime import datetime, timedelta, timezone

import pytest

from app.application.job_progress import JobProgress


BASE = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


def test_progress_estimates_completion_from_elapsed_work():
    job = JobProgress("sermon-1").start(BASE).update(25, "생성 중", BASE.replace(second=30))
    assert job.status == "running"
    assert job.estimated_total_seconds == 120
    assert job.estimated_completion() == BASE + timedelta(seconds=120)


def test_finish_closes_progress_at_one_hundred_percent():
    job = JobProgress("rag-1").start(BASE).update(20, now=BASE.replace(second=10)).finish("완료", BASE + timedelta(seconds=60))
    assert job.status == "completed"
    assert job.percent == 100
    assert job.estimated_completion() is None


def test_failed_and_cancelled_jobs_cannot_be_updated():
    for status in ("failed", "cancelled"):
        job = JobProgress("job").start(BASE).stop(status, "중단")
        with pytest.raises(ValueError, match="진행률"):
            job.update(50)


def test_progress_rejects_invalid_percentage():
    job = JobProgress("job").start(BASE)
    with pytest.raises(ValueError, match="0에서 100"):
        job.update(101)


def test_progress_cannot_move_backwards():
    job = JobProgress("job").start(BASE).update(60, now=BASE.replace(second=10))
    with pytest.raises(ValueError, match="작아질 수 없습니다"):
        job.update(50, now=BASE.replace(second=11))
