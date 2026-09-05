from app.application.job_registry import cancel_job, clear_jobs, fail_job, finish_job, get_job, retry_job, start_job, update_job


def setup_function():
    clear_jobs()


def test_registry_tracks_completion_for_a_generation_id():
    assert start_job("generation-1").status == "running"
    assert finish_job("generation-1", "완료").status == "completed"
    assert get_job("generation-1").percent == 100


def test_registry_tracks_cancellation_without_persistent_storage():
    start_job("outline-1")
    assert cancel_job("outline-1").status == "cancelled"
    assert finish_job("outline-1").status == "cancelled"
    assert get_job("outline-1").estimated_completion() is None


def test_empty_job_id_is_ignored():
    assert start_job("") is None
    assert get_job("") is None


def test_registry_distinguishes_progress_and_failure():
    start_job("failed-generation")
    assert update_job("failed-generation", 40, "근거 준비").percent == 40
    assert fail_job("failed-generation", "모델 오류").status == "failed"
    assert get_job("failed-generation").estimated_completion() is None


def test_registry_retries_only_failed_jobs_and_tracks_attempt_count():
    start_job("retryable")
    assert retry_job("retryable") is None
    fail_job("retryable", "모델 오류", error_code="MODEL_UNAVAILABLE")
    retried = retry_job("retryable")
    assert retried.status == "running"
    assert retried.retry_count == 1
    assert retry_job("retryable") is None
