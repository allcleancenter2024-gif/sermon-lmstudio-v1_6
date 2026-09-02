"""CLI for validating/importing the isolated SBLGNT Apparatus layer."""

from __future__ import annotations

import argparse

from app.apparatus import import_apparatus_directory


def main() -> int:
    parser = argparse.ArgumentParser(description="Import SBLGNT Apparatus into the separate SQLite table")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    report = import_apparatus_directory(persist=not args.validate_only)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
