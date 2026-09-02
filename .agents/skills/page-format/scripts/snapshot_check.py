from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def main() -> int:
    actual = hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()
    expected = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
    print("MATCH" if actual == expected else f"MISMATCH {actual}")
    return 0 if actual == expected else 1


if __name__ == "__main__": raise SystemExit(main())
