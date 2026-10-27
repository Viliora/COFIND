#!/usr/bin/env python3
"""
List or rewrite commit messages that contain Cursor co-author trailers.

Default: dry-run (print affected SHAs). Use --apply with git-filter-repo installed.

WARNING: --apply rewrites history; you must force-push and coordinate with collaborators.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRIP_MODULE = ROOT / "scripts" / "githooks" / "strip_cursor_coauthor.py"

_CURSOR_MARKER = re.compile(r"cursoragent@cursor\.com", re.I)


def _run(cmd: list[str], *, cwd: Path) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True, encoding="utf-8", errors="replace")


def affected_commits(cwd: Path, rev: str) -> list[tuple[str, str, str]]:
    out = _run(["git", "rev-list", rev], cwd=cwd)
    hits: list[tuple[str, str, str]] = []
    for sha in out.splitlines():
        sha = sha.strip()
        if not sha:
            continue
        body = _run(["git", "log", "-1", "--format=%B", sha], cwd=cwd)
        if _CURSOR_MARKER.search(body):
            subject = _run(["git", "log", "-1", "--format=%s", sha], cwd=cwd).strip()
            hits.append((sha, subject, body))
    return hits


def write_filter_repo_callback(dest: Path) -> None:
    dest.write_text(
        '''\
def message(message, metadata):
    import re
    pat = re.compile(
        r"^Co-authored-by:\\s*Cursor\\s*<cursoragent@cursor\\.com>\\s*\\r?\\n?",
        re.IGNORECASE | re.MULTILINE,
    )
    cleaned = pat.sub("", message)
    cleaned = re.sub(r"\\n{3,}", "\\n\\n", cleaned)
    return cleaned.rstrip() + "\\n"
''',
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rev",
        default="--all",
        help='Revision range passed to git rev-list (default: --all)',
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Run git filter-repo (requires git-filter-repo on PATH)",
    )
    args = parser.parse_args()
    cwd = ROOT

    hits = affected_commits(cwd, args.rev)
    if not hits:
        print("No commits contain cursoragent@cursor.com in the message.")
        return 0

    print(f"Found {len(hits)} commit(s) with Cursor co-author trailer:\n")
    for sha, subject, _ in hits:
        on_remote = ""
        try:
            _run(["git", "merge-base", "--is-ancestor", sha, "origin/main"], cwd=cwd)
            on_remote = " [on origin/main ancestry]"
        except subprocess.CalledProcessError:
            on_remote = " [not on origin/main]"
        print(f"  {sha[:12]}  {subject}{on_remote}")

    if not args.apply:
        print(
            "\nDry-run only. To rewrite messages locally, install git-filter-repo then:\n"
            f"  python {Path(__file__).as_posix()} --apply\n"
            "Then inspect with git log, and ONLY if you accept the risks:\n"
            "  git push --force-with-lease origin main"
        )
        return 0

    status = _run(["git", "status", "--porcelain"], cwd=cwd)
    if status.strip():
        print(
            "ERROR: working tree tidak bersih. Commit atau stash dulu agar kode tidak ikut risiko.\n"
            "Hanya pesan commit yang diubah, tapi filter-repo menolak tree kotor.",
            file=sys.stderr,
        )
        return 1

    try:
        subprocess.run(["git", "filter-repo", "--version"], cwd=cwd, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "git-filter-repo not found. Install: pip install git-filter-repo\\n"
            "Or rewrite the single unpushed commit: git commit --amend (hook will strip trailer)",
            file=sys.stderr,
        )
        return 1

    callback = cwd / ".git" / "filter-repo-cursor-coauthor-callback.py"
    write_filter_repo_callback(callback)
    print("Running git filter-repo (this rewrites all commit SHAs)...")
    subprocess.check_call(
        [
            "git",
            "filter-repo",
            "--force",
            f"--message-callback={callback}",
        ],
        cwd=cwd,
    )
    callback.unlink(missing_ok=True)
    print("Done. Verify: git log -5 --format=%B")
    print("RISK: force-push rewrites remote; tell collaborators to re-clone or reset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
