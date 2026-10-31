#!/usr/bin/env python3
"""stdin/stdout filter for git filter-branch --msg-filter."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "githooks"))
from strip_cursor_coauthor import strip_cursor_coauthor  # noqa: E402


def main() -> int:
    raw = sys.stdin.buffer.read()
    if not raw:
        return 0
    text = raw.decode("utf-8", errors="replace")
    sys.stdout.buffer.write(strip_cursor_coauthor(text).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
