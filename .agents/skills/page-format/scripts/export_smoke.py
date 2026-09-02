from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    if not path.is_file():
        print("MISSING")
        return 1
    if path.suffix.lower() == ".pdf":
        data = path.read_bytes()
        pages = data.count(b"/Type /Page")
        ok = data.startswith(b"%PDF") and pages > 0
        print(f"{'VALID' if ok else 'INVALID'} PDF pages={pages}")
        return 0 if ok else 1
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                data = archive.read("word/document.xml")
            ok = b"w:document" in data and b"w:body" in data
        except (KeyError, zipfile.BadZipFile):
            ok = False
        print("VALID DOCX" if ok else "INVALID DOCX")
        return 0 if ok else 1
    print("UNSUPPORTED")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
