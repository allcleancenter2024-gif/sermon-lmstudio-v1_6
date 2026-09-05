"""Small adapters connecting HTTP workflow IDs to the Job Registry."""

from app.application.job_registry import fail_job, finish_job, start_job, update_job


class GenerationJobAdapter:
    def __init__(self, job_id: str, kind: str):
        self.job_id = str(job_id or "").strip()
        self.kind = kind

    @classmethod
    def from_request(cls, request, kind: str) -> "GenerationJobAdapter":
        job_id = request.headers.get("X-Generation-Id", "") if request else ""
        return cls(job_id, kind)

    def start(self):
        return start_job(self.job_id)

    def complete(self, message: str = ""):
        return finish_job(self.job_id, message)

    def update(self, percent: int, message: str = ""):
        return update_job(self.job_id, percent, message)

    def fail(self, message: str = "작업이 실패했습니다."):
        return fail_job(self.job_id, message)

    def abort(self, message: str = "작업이 사전 검증에서 중단되었습니다."):
        """Record a preflight failure before the main generation try block."""
        return self.fail(message)
