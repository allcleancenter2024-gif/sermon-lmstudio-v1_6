from __future__ import annotations

import re
import sys
from html.parser import HTMLParser


class Validator(HTMLParser):
    def __init__(self) -> None:
        super().__init__(); self.h1 = 0; self.errors: list[str] = []
    def handle_starttag(self, tag, attrs):
        if tag == "h1": self.h1 += 1
        values = {key.lower(): str(value or "") for key, value in attrs}
        if tag == "script" or any(key.lower().startswith("on") for key in values): self.errors.append("unsafe script or inline event")
        if any(re.match(r"^javascript:", value, re.I) for value in values.values()): self.errors.append("javascript URL")


def main() -> int:
    parser = Validator(); parser.feed(open(sys.argv[1], encoding="utf-8").read())
    if parser.h1 != 1: parser.errors.append("HTML must contain exactly one H1")
    if parser.errors: print("INVALID\n" + "\n".join(parser.errors)); return 1
    print("VALID"); return 0


if __name__ == "__main__": raise SystemExit(main())
