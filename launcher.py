from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from app.main import APP_VERSION, app, runtime_readiness
from app.core import get_lmstudio_url
from app.lmstudio_control import start_local_server


APP_URL = "http://127.0.0.1:8000"
RUNTIME_URL = APP_URL + "/api/runtime"
APP_PORT = 8000
PORT_SEARCH_LIMIT = 20


def _version_tuple(value: str) -> tuple[int, int, int] | None:
    """Parse the numeric app version used to prevent accidental downgrade takeovers."""
    match = re.fullmatch(r"[vV]?(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(value or "").strip())
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _runtime_info(timeout: float = 1.0) -> dict | None:
    try:
        with urllib.request.urlopen(RUNTIME_URL, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result if isinstance(result, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _is_sermon_runtime(info: dict | None) -> bool:
    if not isinstance(info, dict):
        return False
    minutes = info.get("supported_minutes")
    return bool(
        str(info.get("app_version") or "").strip()
        and isinstance(minutes, list)
        and 15 in minutes
        and str(info.get("local_url") or "").startswith(APP_URL)
    )


def _running_version(timeout: float = 1.0) -> str | None:
    info = _runtime_info(timeout)
    return (str(info.get("app_version") or "") or None) if _is_sermon_runtime(info) else None


def _port_in_use(host: str = "127.0.0.1", port: int = APP_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def _port_can_bind(host: str = "127.0.0.1", port: int = APP_PORT) -> bool:
    """Check the real bind operation, including Windows excluded-port ranges."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        return True
    except OSError:
        return False


def _select_app_port() -> int:
    """Keep port 8000 when possible, otherwise select a free local fallback."""
    if _port_can_bind(port=APP_PORT):
        return APP_PORT
    for candidate in range(APP_PORT + 1, APP_PORT + PORT_SEARCH_LIMIT + 1):
        if not _port_in_use(port=candidate) and _port_can_bind(port=candidate):
            return candidate
    return APP_PORT


def _windows_listener_pids(port: int = APP_PORT) -> list[int]:
    if os.name != "nt":
        return []
    command = (
        f"Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty OwningProcess -Unique"
    )
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for line in result.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid > 0 and pid not in pids:
            pids.append(pid)
    return pids


def _windows_process_name(pid: int) -> str:
    if os.name != "nt" or pid <= 0:
        return ""
    command = f"(Get-Process -Id {int(pid)} -ErrorAction Stop).ProcessName"
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else ""


def _allowed_old_server_process(name: str) -> bool:
    value = name.strip().lower().removesuffix(".exe")
    return value in {"python", "pythonw", "sermonlmstudio"}


def _stop_windows_pid(pid: int) -> bool:
    if os.name != "nt" or pid <= 0:
        return False
    command = f"Stop-Process -Id {int(pid)} -ErrorAction Stop"
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _offer_to_stop_old_server(info: dict, automatic: bool = False) -> bool:
    old_version = str(info.get("app_version") or "unknown")
    if os.name != "nt":
        print(f"Older sermon server V{old_version} is using port {APP_PORT}. Stop it first.")
        return False
    pids = _windows_listener_pids()
    if len(pids) != 1:
        print(f"Safety stop: expected one listener on port {APP_PORT}, found {len(pids)}. Nothing was terminated.")
        return False
    pid = pids[0]
    process_name = _windows_process_name(pid)
    if not _allowed_old_server_process(process_name):
        print(f"Safety stop: port {APP_PORT} belongs to '{process_name or 'unknown'}' (PID {pid}). Nothing was terminated.")
        return False
    if automatic:
        print(f"Verified older sermon server V{old_version} ({process_name}, PID {pid}). Replacing it with V{APP_VERSION}...")
    else:
        answer = input(f"Verified old sermon server V{old_version} ({process_name}, PID {pid}). Stop it and start V{APP_VERSION}? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Cancelled. The old server was not changed.")
            return False
    if _windows_listener_pids() != [pid] or _windows_process_name(pid) != process_name:
        print(f"Safety stop: the listener on port {APP_PORT} changed before confirmation. Nothing was terminated.")
        return False
    if not _stop_windows_pid(pid):
        print(f"Could not stop PID {pid}. Close the old server window with Ctrl+C and try again.")
        return False
    for _ in range(20):
        if not _port_in_use():
            print(f"Old sermon server V{old_version} stopped. Port {APP_PORT} is ready.")
            return True
        time.sleep(0.25)
    print(f"PID {pid} was stopped but port {APP_PORT} is still busy. Nothing else will be terminated.")
    return False


def _open_browser_when_ready() -> None:
    for _ in range(120):
        if _running_version(1.0) == APP_VERSION:
            webbrowser.open(APP_URL)
            return
        time.sleep(0.5)


def _prepare_lmstudio_server() -> None:
    """Best-effort localhost startup; failures never prevent the sermon UI from opening."""
    try:
        result = start_local_server(get_lmstudio_url(), wait_seconds=8)
        mark = "OK" if result.get("port_open") else "ACTION"
        print(f"LM Studio [{mark}]: {result.get('message', '')}")
    except (OSError, ValueError) as exc:
        print(f"LM Studio [ACTION]: 자동 시작 점검 실패: {exc}")


def main() -> int:
    global APP_PORT, APP_URL, RUNTIME_URL

    if "--version" in sys.argv[1:]:
        print(APP_VERSION)
        return 0
    if "--diagnose" in sys.argv[1:]:
        result = runtime_readiness()
        print(f"Sermon LM Studio V{APP_VERSION} readiness")
        for step in result.get("steps", []):
            mark = {"pass": "OK", "warn": "WARN", "fail": "FAIL"}.get(step.get("state"), "?")
            print(f"[{mark}] {step.get('label')}: {step.get('detail')}")
        print(f"User data: {result.get('user_data_root', '')}")
        print(f"LM Studio: {result.get('lmstudio_url', '')}")
        return 0 if result.get("ready_for_generation") else 4
    runtime = _runtime_info()
    running = str(runtime.get("app_version") or "") if _is_sermon_runtime(runtime) else None
    if running == APP_VERSION:
        print(f"Sermon LM Studio V{APP_VERSION} is already running. Opening browser...")
        webbrowser.open(APP_URL)
        return 0
    if running:
        running_tuple = _version_tuple(running)
        current_tuple = _version_tuple(APP_VERSION)
        if running_tuple and current_tuple and running_tuple > current_tuple:
            print(f"A newer sermon server V{running} is already using port {APP_PORT}.")
            print(f"V{APP_VERSION} will not replace a newer version. Use the newer server window instead.")
            return 5
        automatic_upgrade = bool(running_tuple and current_tuple and running_tuple < current_tuple)
        if not _offer_to_stop_old_server(runtime, automatic=automatic_upgrade):
            input("Press Enter to close...")
            return 2
    elif _port_in_use():
        print(f"ERROR: Port {APP_PORT} is used by a program that is not a verified sermon server.")
        print("For safety, this program will not terminate it. Close that program manually and try again.")
        input("Press Enter to close...")
        return 3

    selected_port = _select_app_port()
    if selected_port != APP_PORT:
        APP_PORT = selected_port
        APP_URL = f"http://127.0.0.1:{APP_PORT}"
        RUNTIME_URL = APP_URL + "/api/runtime"
        print(f"Port 8000 is not bindable on this Windows system. Using local port {APP_PORT}.")

    print(f"Sermon LM Studio V{APP_VERSION}")
    print(f"Local web app: {APP_URL}")
    print("LM Studio default: http://127.0.0.1:12345/v1")
    print("Keep this window open while using the application.\n")
    _prepare_lmstudio_server()
    threading.Thread(target=_open_browser_when_ready, daemon=True).start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=APP_PORT, log_level="info")
    except OSError as exc:
        print(f"Server startup failed: {exc}")
        input("Press Enter to close...")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
