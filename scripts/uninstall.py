#!/usr/bin/env python3
"""Preview and remove Codex Tempo managed files, preserving user data."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit("Python 3.11+ is required")

MANAGED_KEYS = {"enabled", "max_concurrent_threads_per_session", "default_subagent_model", "default_subagent_reasoning_effort", "interrupt_message"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, help="Codex home (defaults to CODEX_HOME or ~/.codex)")
    parser.add_argument("--yes", action="store_true", help="confirm after displaying the removal plan")
    args = parser.parse_args()
    home = args.home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    targets = [home / "AGENTS.md"]
    targets += [home / "agents" / f"{name}.toml" for name in ("adaptive_architect", "escalation", "implementer", "repo_scout", "reviewer", "test_fixer")]
    targets += [home / "skills" / name / "SKILL.md" for name in ("adaptive-codex", "codex-app-server", "mco-review")]
    targets += [home / "tools" / "adaptive-codex" / f"{name}.py" for name in ("quota_guard", "quota_snapshot", "mco_gate")]
    targets = [p for p in targets if p.exists()]
    print("Files to remove (all are backed up first):")
    for path in targets:
        print(f"- {path}")
    config = home / "config.toml"
    if not args.yes:
        if input("Back up and remove these managed files? [y/N] ").strip().lower() not in {"y", "yes", "д", "да"}:
            print("Cancelled.")
            return 0
    backup = home / "backups" / "codex-tempo-uninstall" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prior_root = home / "backups" / "adaptive-codex-install"
    for path in targets:
        dest = backup / path.relative_to(home)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    restored = 0
    for path in targets:
        relative = path.relative_to(home)
        prior = sorted(prior_root.glob(f"*/{relative}")) if prior_root.exists() else []
        if prior:
            shutil.copy2(prior[-1], path)
            restored += 1
        else:
            path.unlink(missing_ok=True)
    for parent in sorted({p.parent for p in targets}, key=lambda p: len(p.parts), reverse=True):
        try:
            parent.rmdir()
        except OSError:
            pass
    print(f"Removed {len(targets) - restored} package files and restored {restored} previous user files. Backup: {backup}")
    print("Remove plugin separately with: codex plugin remove adaptive-quota@adaptive-codex")
    print("Global config.toml was preserved to protect user settings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
