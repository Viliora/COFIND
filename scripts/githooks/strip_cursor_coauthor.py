#!/usr/bin/env python3
"""Remove Cursor agent Co-authored-by trailers from a commit message file."""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Cursor IDE / agent trailer (exact + common spacing variants)
_CURSOR_COAUTHOR = re.compile(
    r"^Co-authored-by:\s*Cursor\s*<cursoragent@cursor\.com>\s*\r?\n?",
    re.IGNORECASE | re.MULTILINE,
)


def strip_cursor_coauthor(text: str) -> str:
    cleaned = _CURSOR_COAUTHOR.sub("", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.rstrip() + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: strip_cursor_coauthor.py <commit-msg-file>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        return 0
    raw = path.read_text(encoding="utf-8", errors="replace")
    new = strip_cursor_coauthor(raw)
    if new != raw:
        path.write_text(new, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
