#!/usr/bin/env python
"""Jalankan unittest discover (tests/ + *_checks.py) dan pytest tests/."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    check_modules = sorted(p.stem for p in (ROOT / "tests").glob("*_checks.py"))
    check_cmd = [sys.executable, "-m", "unittest", "-v", *check_modules]
    steps = [
        ("unittest checks", check_cmd),
        (
            "unittest tests",
            [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
        ),
        (
            "pytest tests",
            [sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q"],
        ),
    ]
    code = 0
    for label, cmd in steps:
        print(f"\n=== {label} ===", flush=True)
        rc = subprocess.call(cmd, cwd=ROOT)
        if rc != 0:
            code = rc
    return code


if __name__ == "__main__":
    raise SystemExit(main())
