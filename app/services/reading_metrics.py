"""Pure reading-duration metrics used by project and sermon workflows."""

from __future__ import annotations

import re


def estimate_minutes(text: str, chars_per_minute: int = 330) -> float:
    """Estimate reading time from non-whitespace characters."""
    visible = len(re.sub(r"\s+", "", text))
    return round(visible / max(chars_per_minute, 1), 1)
