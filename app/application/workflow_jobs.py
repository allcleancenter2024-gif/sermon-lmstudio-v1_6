"""Small adapters connecting HTTP workflow IDs to the Job Registry."""

from app.application.job_registry import finish_job, start_job


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
