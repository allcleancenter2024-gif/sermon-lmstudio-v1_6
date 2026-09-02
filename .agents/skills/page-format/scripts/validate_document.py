from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.formatting.document_model import ContentBlock, Document, Section, Source, validate_document


def main() -> int:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    document = Document(
        data["document_type"], data["title"], data.get("subtitle"), data.get("metadata", {}),
        [Section(x["id"], x["type"], x.get("heading"), [ContentBlock(b["type"], b.get("value", ""), b.get("metadata", {})) for b in x.get("content", [])], x.get("level", 2)) for x in data.get("sections", [])],
        [Source(x["id"], x.get("title"), x.get("reference"), x.get("url"), x.get("provider"), x.get("citation"), x.get("metadata", {})) for x in data.get("sources", [])], data.get("warnings", []),
    )
    errors = validate_document(document)
    if errors:
        print("INVALID")
        print("\n".join(errors))
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
