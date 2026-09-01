from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))


def _default_user_root() -> Path:
    if getattr(sys, "frozen", False) and os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "SermonLMStudio"
        return Path.home() / "AppData" / "Local" / "SermonLMStudio"
    return SOURCE_ROOT


USER_ROOT = Path(os.environ.get("SERMON_USER_ROOT", "")).expanduser() if os.environ.get("SERMON_USER_ROOT") else _default_user_root()
DATA_DIR = USER_ROOT / "data"
EXPORTS_DIR = USER_ROOT / "exports"
BACKUPS_DIR = USER_ROOT / "backups"
USER_FONT_DIR = USER_ROOT / "fonts"
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
USER_FONT_DIR.mkdir(parents=True, exist_ok=True)
