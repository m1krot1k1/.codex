#!/usr/bin/env python3
"""Safely install the managed Codex instructions and named agents."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit("install failed: Python 3.11 or newer is required; select a newer Python interpreter")

REPO_ROOT = Path(__file__).resolve().parents[1]
MANAGED_AGENT_SETTINGS = tomllib.loads((REPO_ROOT / "config" / "agents.toml").read_text())["agents"]
MANAGED_TOOLS = ("quota_guard.py", "quota_snapshot.py", "mco_gate.py")


def merge_agents_config(source: str) -> str:
    parsed = tomllib.loads(source) if source.strip() else {}
    if "agents" not in parsed:
        if any(key.startswith("agents.") for key in parsed):
            raise ValueError("config has [agents.*] tables but no [agents]; refusing an ambiguous merge")
        suffix = "\n" if source and not source.endswith("\n") else ""
        block = "\n[agents]\n" + "".join(
            f"{key} = {json.dumps(value) if isinstance(value, str) else str(value).lower()}\n"
            for key, value in MANAGED_AGENT_SETTINGS.items()
        )
        result = source + suffix + block
        tomllib.loads(result)
        return result

    header = re.search(r"(?m)^\[agents\]\s*(?:#.*)?$", source)
    if not header:
        raise ValueError("could not locate the [agents] table in config.toml")
    next_header = re.search(r"(?m)^\[[^\n]+\]\s*(?:#.*)?$", source[header.end():])
    end = header.end() + next_header.start() if next_header else len(source)
    section = source[header.end():end]
    lines = section.splitlines(keepends=True)
    for key, value in MANAGED_AGENT_SETTINGS.items():
        encoded = json.dumps(value) if isinstance(value, str) else str(value).lower()
        assignment = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)([^#\n]*?)(\s+#.*)?(\n?)$")
        replaced = False
        for index, line in enumerate(lines):
            match = assignment.match(line)
            if match:
                lines[index] = f"{match.group(1)}{encoded}{match.group(3) or ''}{match.group(4)}"
                replaced = True
                break
        if not replaced:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"{key} = {encoded}\n")

    result = source[:header.end()] + "".join(lines) + source[end:]
    tomllib.loads(result)
    return result


def atomic_write(path: Path, content: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temp:
            temp_path = Path(temp.name)
            temp.write(content)
        if mode is not None:
            temp_path.chmod(mode)
        temp_path.replace(path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def install_changes(home: Path, changed: dict[Path, bytes]) -> Path | None:
    """Back up all existing targets first and roll back completed writes on errors."""
    existing = [path for path in changed if path.exists()]
    backup_dir = None
    if existing:
        backup_root = home / "backups" / "adaptive-codex-install"
        backup_root.mkdir(parents=True, exist_ok=True)
        prefix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-")
        backup_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=backup_root))
        for path in existing:
            backup = backup_dir / path.relative_to(home)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)

    written: list[Path] = []
    try:
        for path, content in changed.items():
            mode = path.stat().st_mode & 0o777 if path.exists() else None
            atomic_write(path, content, mode)
            written.append(path)
    except OSError as exc:
        failures = []
        for path in reversed(written):
            try:
                if path in existing:
                    backup = backup_dir / path.relative_to(home)
                    atomic_write(path, backup.read_bytes(), backup.stat().st_mode & 0o777)
                else:
                    path.unlink(missing_ok=True)
            except OSError as rollback_exc:
                failures.append(f"{path}: {rollback_exc}")
        if failures:
            raise OSError(f"{exc}; rollback incomplete ({'; '.join(failures)}); backups: {backup_dir}") from exc
        raise OSError(f"{exc}; completed writes rolled back; backups: {backup_dir}") from exc
    return backup_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, help="Codex home to use (defaults to CODEX_HOME or ~/.codex)")
    parser.add_argument("--dry-run", action="store_true", help="show planned changes without writing files")
    args = parser.parse_args()

    repo = REPO_ROOT
    home = args.home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    targets: dict[Path, bytes] = {
        home / "AGENTS.md": (repo / "AGENTS.md").read_bytes(),
    }
    role_files = sorted((repo / "agents").glob("*.toml"))
    if not role_files:
        parser.error("no agent role TOMLs found under agents/")
    for source_path in role_files:
        targets[home / "agents" / source_path.name] = source_path.read_bytes()

    skill_dirs = sorted(path for path in (repo / "skills").iterdir() if path.is_dir())
    if not skill_dirs:
        parser.error("no managed skills found under skills/")
    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            parser.error(f"skill is missing SKILL.md: {skill_dir}")
        targets[home / "skills" / skill_dir.name / "SKILL.md"] = skill_file.read_bytes()
    for tool_name in MANAGED_TOOLS:
        source_path = repo / "scripts" / tool_name
        if not source_path.is_file():
            parser.error(f"managed tool is missing: {source_path}")
        targets[home / "tools" / "adaptive-codex" / tool_name] = source_path.read_bytes()

    config_path = home / "config.toml"
    old_config = config_path.read_text() if config_path.exists() else ""
    new_config = merge_agents_config(old_config)
    targets[config_path] = new_config.encode()

    changed = {path: content for path, content in targets.items() if not path.exists() or path.read_bytes() != content}
    if not changed:
        print(f"Already up to date: {home}")
        return 0
    if args.dry_run:
        print("Would update:")
        for path in changed:
            print(f"- {path}")
        return 0

    backup_dir = install_changes(home, changed)

    tomllib.loads(config_path.read_text())
    print(f"Installed {len(changed)} managed instruction, role, skill, and tool file(s) under {home}")
    if backup_dir is not None:
        print(f"Backups: {backup_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"install failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
