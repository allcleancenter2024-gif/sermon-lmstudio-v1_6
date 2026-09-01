from __future__ import annotations

import os
import json
import shutil
import socket
import subprocess
import time
import urllib.parse
from pathlib import Path


def local_api_port(base_url: str) -> int:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "http" or (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost"}:
        raise ValueError("LM Studio 자동 시작은 이 PC의 로컬 HTTP 주소만 지원합니다.")
    return int(parsed.port or 12345)


def port_is_open(port: int, timeout: float = 0.35) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def find_lms_cli() -> Path | None:
    """Find only the official LM Studio CLI locations; never scan the whole disk."""
    candidates: list[Path] = []
    discovered = shutil.which("lms") or shutil.which("lms.exe")
    if discovered:
        candidates.append(Path(discovered))
    home = Path.home()
    candidates.extend([home / ".lmstudio" / "bin" / "lms.exe", home / ".lmstudio" / "bin" / "lms"])
    user_profile = os.environ.get("USERPROFILE", "").strip()
    if user_profile:
        candidates.append(Path(user_profile) / ".lmstudio" / "bin" / "lms.exe")
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate.resolve()
    return None


def loaded_model_ids() -> set[str] | None:
    """Return models confirmed by `lms ps --json`; None means CLI verification unavailable."""
    cli = find_lms_cli()
    if cli is None:
        return None
    try:
        result = subprocess.run(
            [str(cli), "ps", "--json"],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode != 0:
            return None
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
    ids: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in {"id", "identifier", "modelidentifier", "model_key", "modelkey"} and isinstance(item, str) and item.strip():
                    ids.add(item.strip())
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return ids


def start_local_server(base_url: str, wait_seconds: float = 12.0) -> dict:
    """Start the localhost-only LM Studio server through the bundled lms CLI."""
    port = local_api_port(base_url)
    cli = find_lms_cli()
    if port_is_open(port):
        return {
            "started": False,
            "port_open": True,
            "port": port,
            "cli": str(cli or ""),
            "message": f"포트 {port}에서 서버가 이미 응답합니다. LM Studio API인지 이어서 확인합니다.",
        }
    if cli is None:
        return {
            "started": False,
            "port_open": False,
            "port": port,
            "cli": "",
            "message": "LM Studio CLI(lms)를 찾지 못했습니다. LM Studio를 한 번 실행한 뒤 다시 시도하세요.",
        }
    try:
        process = subprocess.Popen(
            [str(cli), "server", "start", "--port", str(port), "--bind", "127.0.0.1"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        return {"started": False, "port_open": False, "port": port, "cli": str(cli), "message": f"lms 실행 실패: {exc}"}

    deadline = time.monotonic() + max(1.0, wait_seconds)
    while time.monotonic() < deadline:
        if port_is_open(port):
            return {
                "started": True,
                "port_open": True,
                "port": port,
                "cli": str(cli),
                "message": f"LM Studio Local Server를 로컬 포트 {port}에서 시작했습니다.",
            }
        exit_code = process.poll()
        if exit_code is not None and exit_code != 0:
            detail = ""
            try:
                output = process.communicate(timeout=1)
                stderr = output[1] if isinstance(output, tuple) and len(output) > 1 else ""
                detail = (stderr or "").strip().splitlines()[-1] if isinstance(stderr, str) and stderr else ""
            except (OSError, subprocess.SubprocessError):
                pass
            if "EACCES" in detail or "permission denied" in detail.lower():
                message = (
                    f"LM Studio 서버가 로컬 포트 {port}를 열 권한이 없습니다({detail}). "
                    "LM Studio Developer > Local Server에서 서버를 직접 Start하고, "
                    "Server Port를 12345, Serve on Local Network를 OFF로 설정하세요."
                )
            else:
                message = f"lms 서버 시작 명령이 종료 코드 {exit_code}로 끝났습니다."
                if detail:
                    message += f" 상세: {detail}"
            return {
                "started": False,
                "port_open": False,
                "port": port,
                "cli": str(cli),
                "message": message + " LM Studio를 한 번 직접 실행하고 Runtime을 확인하세요.",
            }
        time.sleep(0.25)
    if process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=2)
        except (OSError, subprocess.SubprocessError):
            try:
                process.kill()
            except OSError:
                pass
    return {
        "started": False,
        "port_open": False,
        "port": port,
        "cli": str(cli),
        "message": "lms 명령을 실행했지만 제한 시간 안에 서버 포트가 열리지 않았습니다. LM Studio의 Developer 화면과 Runtime을 확인하세요.",
    }
