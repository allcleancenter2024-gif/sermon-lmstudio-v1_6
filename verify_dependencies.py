from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIREMENT_FILES = (ROOT / "requirements.txt", ROOT / "requirements-pdf.txt")
STAMP_PATH = ROOT / ".venv" / "sermon-requirements.sha256"
REQUIRED_MODULES = ("fastapi", "uvicorn", "pydantic", "docx", "weasyprint", "reportlab")


def requirements_digest() -> str:
    digest = hashlib.sha256()
    for path in REQUIREMENT_FILES:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def modules_present() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in REQUIRED_MODULES)


def dependencies_current(stamp_path: Path = STAMP_PATH) -> bool:
    try:
        return modules_present() and stamp_path.read_text(encoding="ascii").strip() == requirements_digest()
    except (OSError, UnicodeError):
        return False


def write_stamp(stamp_path: Path = STAMP_PATH) -> int:
    if not modules_present():
        print("[ERROR] One or more required Python packages are still missing.")
        return 1
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_text(requirements_digest() + "\n", encoding="ascii")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--write" in args:
        return write_stamp()
    return 0 if dependencies_current() else 1


if __name__ == "__main__":
    raise SystemExit(main())
