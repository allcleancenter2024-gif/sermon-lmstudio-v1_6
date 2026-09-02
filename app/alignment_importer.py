"""CLI for SBLGNT/MorphGNT alignment diagnostics."""

from __future__ import annotations

import argparse

from app.alignment import align_reference, build_alignment_report
from app.paths import DATA_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Build non-destructive SBLGNT/MorphGNT alignment report")
    parser.add_argument("--reference", help="Check one reference, e.g. JHN 8:32")
    args = parser.parse_args()
    if args.reference:
        print(align_reference(args.reference))
    else:
        report = build_alignment_report(output_path=DATA_DIR / "bible" / "greek" / "derived" / "sblgnt_morphgnt_alignment.json")
        print({"items": report["items"], "counts": report["counts"], "output_path": report["output_path"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
