"""Local application configuration with no dependency on :mod:`app.core`."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from app.constants import DEFAULT_LMSTUDIO_URL, LEGACY_LMSTUDIO_URL
from app.repositories.settings import DB_PATH, get_json, set_json


def normalize_lmstudio_url(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    if not raw:
        raw = DEFAULT_LMSTUDIO_URL
    parsed = urlparse(raw)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("LM Studio 주소는 이 PC의 로컬 HTTP 주소(127.0.0.1/localhost)만 사용할 수 있습니다.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("LM Studio 주소에 계정정보, 쿼리 또는 #fragment를 넣을 수 없습니다.")
    if parsed.path in {"", "/"}:
        raw += "/v1"
    elif parsed.path.rstrip("/") != "/v1":
        raise ValueError("LM Studio 주소는 /v1 경로를 사용해야 합니다. 예: http://127.0.0.1:12345/v1")
    return raw.rstrip("/")


def get_lmstudio_url(db_path: Path = DB_PATH) -> str:
    env_url = os.environ.get("SERMON_LMSTUDIO_URL")
    if env_url:
        try:
            return normalize_lmstudio_url(env_url)
        except ValueError:
            return DEFAULT_LMSTUDIO_URL
    value = get_json("lmstudio_url", db_path)
    if value is None:
        return DEFAULT_LMSTUDIO_URL
    try:
        stored = normalize_lmstudio_url(str(value))
    except (TypeError, ValueError):
        return DEFAULT_LMSTUDIO_URL
    if stored == LEGACY_LMSTUDIO_URL:
        set_json("lmstudio_url", DEFAULT_LMSTUDIO_URL, db_path)
        return DEFAULT_LMSTUDIO_URL
    return stored


def set_lmstudio_url(value: str, db_path: Path = DB_PATH) -> str:
    normalized = normalize_lmstudio_url(value)
    set_json("lmstudio_url", normalized, db_path)
    return normalized
