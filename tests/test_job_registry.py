from app.application.job_registry import cancel_job, clear_jobs, finish_job, get_job, start_job


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
