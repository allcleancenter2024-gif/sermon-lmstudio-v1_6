"""Single source of truth for the product version.

The public APP_VERSION name remains available from app.main and the project
router for backward compatibility.  Keeping the file read dependency-free
allows launch-time verification without importing the application graph.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = PROJECT_ROOT / "VERSION.txt"


def read_app_version() -> str:
    """Read and validate the three-part product version from VERSION.txt."""
    value = VERSION_FILE.read_text(encoding="utf-8-sig").strip()
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise RuntimeError(f"잘못된 제품 버전 형식입니다: {value!r}")
    return value


APP_VERSION = read_app_version()


def app_version_major(version: str = APP_VERSION) -> int:
    """Return the legacy numeric release line used by existing API clients."""
    return int(version.split(".", 1)[0])
