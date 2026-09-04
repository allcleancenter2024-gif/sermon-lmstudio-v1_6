from __future__ import annotations

import sys

from app.version import APP_VERSION


def verify(expected_version: str) -> int:
    expected = expected_version.strip()
    if not expected:
        print("[ERROR] Expected application version is missing.")
        return 9
    if APP_VERSION != expected:
        print(f"[ERROR] Wrong or mixed program folder. Expected V{expected}, actual V{APP_VERSION}.")
        return 6
    print(f"Application import OK - V{APP_VERSION}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    expected = args[1] if len(args) > 1 else ""
    return verify(expected)


if __name__ == "__main__":
    raise SystemExit(main())
