"""CLI for validating/importing the local MorphGNT corpus."""

from __future__ import annotations

import argparse
import json

from app.morphgnt import MORPHGNT_ROOT, import_morphgnt_directory


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or import MorphGNT SBLGNT")
    parser.add_argument("--validate-only", action="store_true", help="parse and validate without database changes")
    parser.add_argument("--import", dest="do_import", action="store_true", help="import normalized tokens into SQLite")
    args = parser.parse_args()
    if not args.validate_only and not args.do_import:
        parser.error("--validate-only 또는 --import 중 하나를 지정하세요.")
    result = import_morphgnt_directory(root=MORPHGNT_ROOT, persist=not args.validate_only)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
