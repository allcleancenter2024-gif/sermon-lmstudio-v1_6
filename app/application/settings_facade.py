"""Application boundary for runtime and provider settings.

This module exposes the existing settings capabilities as one application
contract.  The underlying persistence and LM Studio control implementations
remain unchanged so legacy imports and localhost safety rules are preserved.
"""

from app.core import (
    LMStudioClient,
    calibrate_reading_cpm,
    get_lmstudio_url,
    get_reading_cpm,
    set_lmstudio_url,
    set_reading_cpm,
)
from app.github import get_github_repository_url, set_github_repository_url
from app.lmstudio_control import find_lms_cli, local_api_port, port_is_open, start_local_server

__all__ = [
    "LMStudioClient", "calibrate_reading_cpm", "get_lmstudio_url", "get_reading_cpm",
    "set_lmstudio_url", "set_reading_cpm", "get_github_repository_url",
    "set_github_repository_url", "find_lms_cli", "local_api_port", "port_is_open",
    "start_local_server",
]
