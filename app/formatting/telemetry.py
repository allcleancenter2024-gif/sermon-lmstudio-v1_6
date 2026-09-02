from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from app.paths import USER_ROOT


ERROR_CODES = {"PF_DOC_INVALID", "PF_PROFILE_UNKNOWN", "PF_TEMPLATE_ERROR", "PF_HTML_SECURITY", "PF_PDF_EXPORT", "PF_DOCX_EXPORT", "PF_SOURCE_LOSS", "PF_UNICODE_ERROR", "PF_VISUAL_REGRESSION", "PF_FALLBACK_HTML_RENDER", "PF_FALLBACK_PDF_EXPORT", "PF_FALLBACK_DOCX_EXPORT", "PF_FALLBACK_PROFILE_UNSUPPORTED"}


def record_event(event: str, *, format: str | None = None, profile: str | None = None, theme: str | None = None, preset: str | None = None, duration_ms: int | None = None, output_size: int | None = None, status: str = "ok", error_code: str | None = None, quality_score: int | None = None) -> dict[str, Any]:
    safe_code = error_code if error_code in ERROR_CODES else None
    data = {"render_id": uuid.uuid4().hex, "event": event, "format": format, "profile": profile, "theme": theme, "preset": preset, "duration_ms": duration_ms, "output_size": output_size, "status": status, "error_code": safe_code, "quality_score": quality_score, "timestamp": int(time.time())}
    path = USER_ROOT / "data" / "page_format_telemetry.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")
    return data


def summarize_events(path: Path | None = None) -> dict[str, Any]:
    """Aggregate technical observation metrics without reading document content."""
    source = path or (USER_ROOT / "data" / "page_format_telemetry.jsonl")
    rows: list[dict[str, Any]] = []
    if source.exists():
        for line in source.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict): rows.append(item)
    completed = [row for row in rows if row.get("event") == "render_completed"]
    fallback = [row for row in rows if row.get("event") == "fallback_used"]
    durations = sorted(int(row["duration_ms"]) for row in completed if isinstance(row.get("duration_ms"), (int, float)))
    scores = [int(row["quality_score"]) for row in completed if isinstance(row.get("quality_score"), (int, float))]
    def percentile(values: list[int], ratio: float) -> int | None:
        if not values: return None
        return values[min(len(values) - 1, max(0, int((len(values) - 1) * ratio)))]
    return {"total_events": len(rows), "render_count": len(completed), "fallback_count": len(fallback), "fallback_rate": round(len(fallback) / len(completed), 4) if completed else 0.0, "avg_quality_score": round(sum(scores) / len(scores), 2) if scores else None, "p50_render_ms": percentile(durations, 0.50), "p95_render_ms": percentile(durations, 0.95), "formats": {fmt: sum(1 for row in completed if row.get("format") == fmt) for fmt in sorted({str(row.get("format")) for row in completed if row.get("format")})}}
