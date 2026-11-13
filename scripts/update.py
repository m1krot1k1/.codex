#!/usr/bin/env python3
"""Safely check for or apply updates to a clean Git checkout."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, check=check, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="fast-forward a clean checkout to origin/main")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not (root / ".git").exists():
        parser.error("source checkout is required")
    if run(root, "status", "--porcelain").stdout.strip():
        print("Update stopped: local changes are present. Commit or back them up before updating.", file=sys.stderr)
        return 2
    branch = run(root, "branch", "--show-current").stdout.strip()
    if branch != "main":
        print(f"Update stopped: expected branch main, found {branch or '(detached HEAD)' }.", file=sys.stderr)
        return 2
    run(root, "fetch", "origin", "main")
    behind = run(root, "rev-list", "--count", "HEAD..origin/main").stdout.strip()
    if behind == "0":
        print("Already up to date.")
        return 0
    print(f"{behind} update(s) available on origin/main.")
    if not args.apply:
        print("Inspect changes, then run ./install.sh --update to apply them.")
        return 0
    ahead = run(root, "rev-list", "--count", "origin/main..HEAD").stdout.strip()
    if ahead != "0":
        print("Update stopped: local main has commits not present on origin/main.", file=sys.stderr)
        return 2
    run(root, "merge", "--ff-only", "origin/main")
    print("Updated source checkout. Run ./install.sh to synchronize Codex files and the plugin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
