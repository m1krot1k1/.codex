#!/usr/bin/env python3
"""Validate managed Codex TOML files and required role metadata."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

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
    for phrase in ("get_usage_limits", "100% остатка", "Fast", "время до сброса"):
        if phrase not in quota:
            raise ValueError(f"AGENTS.md is missing required policy text: {phrase}")
    print(f"Validated {len(EXPECTED)} agent roles, agent defaults, and quota/reset/Fast policy.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
