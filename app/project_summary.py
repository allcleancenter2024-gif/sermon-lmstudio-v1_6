"""Read-only project change summary shared by release notes and dashboard."""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=4)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _area(path: str) -> str:
    path = path.replace("\\", "/")
    if path.startswith("tests/"): return "테스트·검증"
    if path.startswith("static/") or path.startswith("templates/"): return "화면·워크플로우"
    if path.startswith("app/providers/"): return "LM Studio·Provider"
    if path.startswith("app/rag/") or "rag" in path.lower(): return "RAG·검색"
    if path.startswith("app/"): return "설교·근거·저장"
    if path.startswith("scripts/"): return "운영·배포"
    return "프로젝트 설정"


def build_project_summary(root: Path, app_version: str) -> dict:
    raw = _git(root, "log", "-8", "--date=short", "--format=%H%x1f%h%x1f%ad%x1f%s")
    commits = []
    for line in raw.splitlines():
        parts = line.split("\x1f", 3)
        if len(parts) != 4: continue
        full, short, date, subject = parts
        files = [x for x in _git(root, "show", "--format=", "--name-only", full).splitlines() if x]
        commits.append({"hash": short, "date": date, "subject": subject, "files": files, "areas": list(dict.fromkeys(_area(x) for x in files))})
    latest = commits[0] if commits else None
    return {"app_version": app_version, "git_available": bool(raw), "working_tree": "clean" if not _git(root, "status", "--porcelain") else "modified", "latest": latest, "commits": commits, "test_note": "표준 scripts/run_tests.ps1 실행 결과는 작업 완료 시 확인합니다."}
