"""Read-only local Git/GitHub readiness helpers.

This module deliberately does not run git init, create remotes, commit, or push.
Those operations change user data or external state and require an explicit
separate workflow.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse

from app.repositories.settings import DB_PATH, get_json, set_json

GITHUB_SETTING_KEY = "github_repository_url"
DEFAULT_GITHUB_REPOSITORY_URL = "https://github.com/allcleancenter2024-gif/sermon-lmstudio-v1_6"


def get_github_repository_url(db_path: Path = DB_PATH) -> str:
    value = get_json(GITHUB_SETTING_KEY, db_path)
    configured = str(value).strip() if value else ""
    if not configured or configured.rstrip("/").lower() == "https://github.com/keunho2025/sermon-lmstudio-v1_6":
        if configured != DEFAULT_GITHUB_REPOSITORY_URL:
            set_json(GITHUB_SETTING_KEY, DEFAULT_GITHUB_REPOSITORY_URL, db_path)
        return DEFAULT_GITHUB_REPOSITORY_URL
    return configured


def normalize_github_repository_url(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("GitHub 저장소 주소는 https://github.com/소유자/저장소 형식이어야 합니다.")
    if parsed.query or parsed.fragment or not parsed.path.strip("/"):
        raise ValueError("GitHub 저장소 주소에 쿼리·fragment를 넣을 수 없습니다.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise ValueError("GitHub 저장소 주소는 소유자와 저장소 이름을 포함해야 합니다.")
    return f"https://github.com/{parts[0]}/{parts[1]}"


def set_github_repository_url(value: str, db_path: Path = DB_PATH) -> str:
    normalized = normalize_github_repository_url(value)
    set_json(GITHUB_SETTING_KEY, normalized, db_path)
    return normalized


def git_readiness(root: Path) -> dict:
    root = Path(root)
    base = {"repository": False, "branch": "", "remote": "", "detail": ""}
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            shell=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        base["detail"] = "Git 실행 파일을 찾지 못했습니다. Git for Windows 설치를 확인하세요."
        return base
    if probe.returncode != 0:
        base["detail"] = "이 프로젝트 폴더가 Git 작업 트리로 초기화되지 않았습니다."
        return base
    base["repository"] = True
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True, timeout=5, check=False, shell=False)
        remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=root, capture_output=True, text=True, timeout=5, check=False, shell=False)
        base["branch"] = branch.stdout.strip()
        base["remote"] = remote.stdout.strip() if remote.returncode == 0 else ""
        base["detail"] = "로컬 Git 저장소가 확인되었습니다."
    except (OSError, subprocess.TimeoutExpired):
        base["detail"] = "Git 저장소는 확인했지만 세부 상태를 읽지 못했습니다."
    return base


def github_readiness(root: Path, db_path: Path = DB_PATH) -> dict:
    local = git_readiness(root)
    configured = get_github_repository_url(db_path)
    return {
        **local,
        "configured_url": configured,
        "state": "pass" if local["repository"] and (local["remote"] or configured) else "warn",
        "detail": (
            f"로컬 Git 저장소·GitHub 연결 설정 확인 · {local['branch'] or '브랜치 확인 필요'}"
            if local["repository"] and (local["remote"] or configured)
            else ("GitHub 저장소 주소를 설정하면 연결 대상이 보존됩니다. 자동 push는 수행하지 않습니다." if configured else local["detail"] + " GitHub 저장소 주소를 설정할 수 있습니다.")
        ),
    }
