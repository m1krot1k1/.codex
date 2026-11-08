#!/usr/bin/env python3
"""Non-blocking SessionStart hint based only on the sanitized quota snapshot."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

TTL_SECONDS = 15 * 60


def _snapshot_path() -> Path:
    home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return home / "state" / "adaptive-quota.json"


def _context(now: int | None = None) -> str:
    try:
        data = json.loads(_snapshot_path().read_text(encoding="utf-8"))
        current = int(time.time() if now is None else now)
        captured = int(data["capturedAt"])
        age = current - captured
        short = float(data["primaryRemaining"])
        weekly = float(data["weeklyRemaining"])
        short_reset = int(data["primaryResetsAt"])
        weekly_reset = int(data["weeklyResetsAt"])
        if (
            data.get("schemaVersion") != 1
            or age < 0
            or age > TTL_SECONDS
            or not 0 <= short <= 100
            or not 0 <= weekly <= 100
        ):
            raise ValueError("stale or invalid")
        return (
            "Adaptive Codex quota snapshot is fresh: "
            f"short window {short:g}% remaining (reset in {_duration(short_reset - current)}), "
            f"weekly window {weekly:g}% remaining (reset in {_duration(weekly_reset - current)}). "
            "Refresh the official usage meter before each costly phase; shared usage may have changed. "
            "Fast is off by default; consider it manually for an explicitly urgent step when the quota guard permits it."
            + (" A saved reset is reported; never apply it automatically." if data.get("savedResetAvailable") else "")
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return (
            "Adaptive Codex quota snapshot is missing, stale, or invalid. "
            "Read get_usage_limits if available; otherwise use closed mode: Luna Medium, no Astra, "
            "no optional parallel model runs, and Fast off. Do not inspect credential files."
        )


def _duration(seconds: int) -> str:
    minutes = max(0, int(seconds)) // 60
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


if __name__ == "__main__":
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": _context(),
        }
    }, ensure_ascii=False))
