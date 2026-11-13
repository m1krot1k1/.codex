#!/usr/bin/env python3
"""Validate managed Codex TOML files and required role metadata."""

from __future__ import annotations

import sys
import json
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    sys.exit("validation failed: Python 3.11 or newer is required; select a newer Python interpreter")

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "adaptive_architect": ("gpt-6.1-sol", "high"),
    "repo_scout": ("gpt-6-luna", "high"),
    "implementer": ("gpt-6-luna", "medium"),
    "test_fixer": ("gpt-6-luna", "medium"),
    "reviewer": ("gpt-6.1-sol", "medium"),
    "escalation": ("gpt-6-astra", "medium"),
}


def main() -> int:
    config = tomllib.loads((ROOT / "config/agents.toml").read_text())
    agents = config.get("agents", {})
    if (
        agents.get("enabled") is not True
        or agents.get("max_concurrent_threads_per_session") != 2
        or agents.get("default_subagent_model") != "gpt-6-luna"
        or agents.get("default_subagent_reasoning_effort") != "medium"
        or agents.get("interrupt_message") is not True
    ):
        raise ValueError("agent defaults are missing or unexpectedly permissive")
    for name, (model, effort) in EXPECTED.items():
        path = ROOT / "agents" / f"{name}.toml"
        role = tomllib.loads(path.read_text())
        if role.get("name") != name or role.get("model") != model or role.get("model_reasoning_effort") != effort:
            raise ValueError(f"unexpected role settings: {path}")
        if not role.get("description") or not role.get("developer_instructions"):
            raise ValueError(f"incomplete role: {path}")
    quota = (ROOT / "AGENTS.md").read_text()
    for phrase in ("get_usage_limits", "100% остатка", "Fast", "время до сброса", "сброс будет в течение 2 часов"):
        if phrase not in quota:
            raise ValueError(f"AGENTS.md is missing required policy text: {phrase}")
    for skill_dir in sorted((ROOT / "skills").iterdir()):
        skill_file = skill_dir / "SKILL.md"
        text = skill_file.read_text()
        blocks = text.split("---\n", 2) if text.startswith("---\n") else []
        if len(blocks) != 3 or not blocks[1].startswith("name: ") or "\ndescription: " not in blocks[1]:
            raise ValueError(f"skill is missing required name/description frontmatter: {skill_file}")
    plugin_root = ROOT / "plugins" / "adaptive-quota"
    manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text())
    hooks = json.loads((plugin_root / "hooks" / "hooks.json").read_text())
    marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
    if manifest.get("name") != "adaptive-quota" or manifest.get("skills") != "./skills/" or manifest.get("hooks") != "./hooks/hooks.json":
        raise ValueError("plugin manifest is missing its skill or SessionStart hook")
    if "SessionStart" not in hooks.get("hooks", {}):
        raise ValueError("plugin must only add the declared SessionStart reminder hook")
    entries = [entry for entry in marketplace.get("plugins", []) if entry.get("name") == "adaptive-quota"]
    if len(entries) != 1 or entries[0].get("source", {}).get("path") != "./plugins/adaptive-quota":
        raise ValueError("adaptive-quota is missing from the local plugin marketplace")
    if (plugin_root / "skills" / "adaptive-codex" / "SKILL.md").read_bytes() != (ROOT / "skills" / "adaptive-codex" / "SKILL.md").read_bytes():
        raise ValueError("bundled and global adaptive-codex skills must stay in sync")
    catalog_root = ROOT / "plugins" / "codex-tempo"
    catalog = json.loads((catalog_root / ".codex-plugin" / "plugin.json").read_text())
    if catalog.get("name") != "codex-tempo" or catalog.get("skills") != "./skills/":
        raise ValueError("Codex Tempo catalog manifest must be skills-only")
    if catalog.get("interface", {}).get("logo") != "./assets/icon.svg" or catalog["interface"].get("composerIcon") != "./assets/icon.svg":
        raise ValueError("Codex Tempo manifest must include its square listing icon")
    if "hooks" in catalog:
        raise ValueError("Codex catalog package must not include lifecycle hooks")
    for asset in ("assets/icon.svg", "skills/codex-tempo-start/SKILL.md"):
        if not (catalog_root / asset).is_file():
            raise ValueError(f"Codex Tempo catalog package is missing {asset}")
    print(f"Validated {len(EXPECTED)} agent roles, {len(list((ROOT / 'skills').iterdir()))} skills, plugin hooks, agent defaults, and quota/reset/Fast policy.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
