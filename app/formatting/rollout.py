from __future__ import annotations

import hashlib
import os


def rollout_stage() -> str:
    return os.getenv("PAGE_FORMAT_ROLLOUT", "legacy").strip().lower()


def v2_is_selected(render_id: str, stage: str | None = None) -> bool:
    stage = (stage or rollout_stage()).strip().lower()
    if stage in {"internal", "canary", "100", "all", "v2"}: return True
    if stage in {"legacy", "0", "off", "false"}: return False
    try:
        percentage = max(0, min(100, int(stage)))
    except ValueError:
        percentage = 0
    bucket = int(hashlib.sha256(render_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    return bucket < percentage
