#!/usr/bin/env python3
"""Store only a short-lived, credential-free Codex usage snapshot."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_TTL_SECONDS = 15 * 60


def snapshot_path(home: Path | None = None) -> Path:
    root = home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return root / "state" / "adaptive-quota.json"


def record_snapshot(
    path: Path,
    *,
    primary_used_percent: float,
    primary_resets_at: int,
    weekly_used_percent: float,
    weekly_resets_at: int,
    saved_reset_available: bool = False,
    saved_reset_expires_at: int | None = None,
    captured_at: int | None = None,
) -> dict:
    for name, value in (("primary", primary_used_percent), ("weekly", weekly_used_percent)):
        if not 0 <= value <= 100:
            raise ValueError(f"{name} used percent must be between 0 and 100")
    if primary_resets_at <= 0 or weekly_resets_at <= 0:
        raise ValueError("reset timestamps must be positive Unix seconds")
    if saved_reset_expires_at is not None and saved_reset_expires_at <= 0:
        raise ValueError("saved reset expiry must be positive Unix seconds")

    captured = int(time.time() if captured_at is None else captured_at)
    if captured <= 0:
        raise ValueError("captured_at must be a positive Unix timestamp")
    data = {
        "schemaVersion": SCHEMA_VERSION,
        "capturedAt": captured,
        "primaryRemaining": round(100 - primary_used_percent, 2),
        "primaryResetsAt": int(primary_resets_at),
        "weeklyRemaining": round(100 - weekly_used_percent, 2),
        "weeklyResetsAt": int(weekly_resets_at),
        "savedResetAvailable": bool(saved_reset_available),
        "savedResetExpiresAt": int(saved_reset_expires_at) if saved_reset_expires_at else None,
    }
    parent_existed = path.parent.exists()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not parent_existed:
        path.parent.chmod(0o700)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        json.dump(data, temp, separators=(",", ":"))
        temp.write("\n")
        temp_path = Path(temp.name)
    temp_path.chmod(0o600)
    temp_path.replace(path)
    path.chmod(0o600)
    return data


def read_snapshot(path: Path, *, now: int | None = None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> tuple[dict | None, bool, int | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schemaVersion") != SCHEMA_VERSION:
            return None, False, None
        required = ("capturedAt", "primaryRemaining", "primaryResetsAt", "weeklyRemaining", "weeklyResetsAt")
        if any(key not in data for key in required):
            return None, False, None
        for key in ("capturedAt", "primaryResetsAt", "weeklyResetsAt"):
            if isinstance(data[key], bool) or int(data[key]) <= 0:
                return None, False, None
        if not (0 <= float(data["primaryRemaining"]) <= 100 and 0 <= float(data["weeklyRemaining"]) <= 100):
            return None, False, None
        current = int(time.time() if now is None else now)
        captured = int(data["capturedAt"])
        if captured > current + 300:
            return None, False, None
        age = max(0, current - captured)
        return data, age <= ttl_seconds, age
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None, False, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record", help="store a sanitized usage reading")
    record.add_argument("--primary-used-percent", type=float, required=True)
    record.add_argument("--primary-resets-at", type=int, required=True)
    record.add_argument("--weekly-used-percent", type=float, required=True)
    record.add_argument("--weekly-resets-at", type=int, required=True)
    record.add_argument("--saved-reset-available", action="store_true")
    record.add_argument("--saved-reset-expires-at", type=int)
    record.add_argument("--path", type=Path, help="override the default snapshot path")
    status = sub.add_parser("status", help="display freshness and safe summary")
    status.add_argument("--path", type=Path, help="override the default snapshot path")
    status.add_argument("--ttl-minutes", type=int, default=15)
    args = parser.parse_args()
    path = args.path or snapshot_path()

    if args.command == "record":
        data = record_snapshot(
            path,
            primary_used_percent=args.primary_used_percent,
            primary_resets_at=args.primary_resets_at,
            weekly_used_percent=args.weekly_used_percent,
            weekly_resets_at=args.weekly_resets_at,
            saved_reset_available=args.saved_reset_available,
            saved_reset_expires_at=args.saved_reset_expires_at,
        )
        print(f"Saved sanitized quota snapshot to {path}; no account ID or credentials were stored.")
        print(f"Short window: {data['primaryRemaining']}% remaining; weekly: {data['weeklyRemaining']}% remaining.")
        return 0

    data, fresh, age = read_snapshot(path, ttl_seconds=max(0, args.ttl_minutes) * 60)
    if data is None:
        print("No valid quota snapshot. Call get_usage_limits if available; otherwise use the closed mode.")
        return 2
    print(f"Snapshot age: {age // 60}m; {'fresh' if fresh else 'stale'}.")
    print(f"Short window: {data['primaryRemaining']}% remaining; weekly: {data['weeklyRemaining']}% remaining.")
    print(f"Saved reset available: {'yes' if data.get('savedResetAvailable') else 'no'}.")
    return 0 if fresh else 2


if __name__ == "__main__":
    raise SystemExit(main())
