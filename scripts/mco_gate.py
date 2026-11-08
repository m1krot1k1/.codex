#!/usr/bin/env python3
"""Opt-in, quota-gated, read-only MCO review launcher.

This helper is deliberately narrower than MCO: it supports review only, requires
an explicit provider team and execution flag, and fails closed on missing or
stale usage data. It never installs MCO or chooses providers/models.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from quota_snapshot import DEFAULT_TTL_SECONDS, read_snapshot, snapshot_path

SUPPORTED_PROVIDERS = {
    "agy", "claude", "codex", "copilot", "cursor", "gemini", "grok",
    "hermes", "kimi", "opencode", "pi", "qwen",
}
PROVIDER_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
MIN_REMAINING_PERCENT = 50
MAX_PROMPT_CHARS = 8_000
MAX_PROVIDERS = 3


def parse_providers(value: str) -> list[str]:
    providers = [item.strip().lower() for item in value.split(",") if item.strip()]
    if len(providers) < 2 or len(providers) > MAX_PROVIDERS or len(set(providers)) != len(providers):
        raise ValueError(f"choose two or three different providers (maximum {MAX_PROVIDERS})")
    invalid = [name for name in providers if not PROVIDER_RE.fullmatch(name) or name not in SUPPORTED_PROVIDERS]
    if invalid:
        raise ValueError(f"unsupported provider ID(s): {', '.join(invalid)}")
    return providers


def parse_target_paths(value: str, repo: Path) -> list[str]:
    requested = [item.strip() for item in value.split(",") if item.strip()]
    if not requested or "." in requested:
        raise ValueError("name one or more explicit target paths; reviewing the whole repository is not allowed")
    resolved = []
    for item in requested:
        candidate = (repo / item).resolve()
        if not candidate.is_relative_to(repo) or not candidate.exists():
            raise ValueError(f"target path must exist inside the repository: {item}")
        relative = candidate.relative_to(repo).as_posix()
        if relative not in resolved:
            resolved.append(relative)
    return resolved


def build_command(mco_bin: str, repo: Path, providers: list[str], target_paths: list[str], prompt: str) -> list[str]:
    return [
        mco_bin,
        "review",
        "--repo",
        str(repo),
        "--prompt",
        prompt,
        "--providers",
        ",".join(providers),
        "--target-paths",
        ",".join(target_paths),
        "--allow-paths",
        ",".join(target_paths),
        "--execution-mode",
        "read_only",
        "--enforcement-mode",
        "strict",
        "--review-hard-timeout",
        "300",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="fresh sanitized quota snapshot; defaults to CODEX_HOME/state/adaptive-quota.json")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository to review (default: current directory)")
    parser.add_argument("--providers", required=True, help="explicit comma-separated MCO provider IDs (at least two)")
    parser.add_argument("--confirm-provider-team", help="repeat the exact provider list after confirming it with the user")
    parser.add_argument("--target-paths", required=True, help="explicit comma-separated files/directories inside --repo; whole-repository scope is blocked")
    parser.add_argument("--prompt-file", type=Path, required=True, help="UTF-8 review prompt file; only this file's contents are sent")
    parser.add_argument("--execute", action="store_true", help="actually dispatch the external model review; otherwise show a no-call preview")
    args = parser.parse_args()

    try:
        providers = parse_providers(args.providers)
        repo = args.repo.resolve()
        target_paths = parse_target_paths(args.target_paths, repo)
    except ValueError as exc:
        parser.error(str(exc))

    snapshot_file = args.snapshot or snapshot_path()
    quota, fresh, age = read_snapshot(snapshot_file, ttl_seconds=DEFAULT_TTL_SECONDS)
    if quota is None or not fresh:
        print("DENIED: usage is unknown or the snapshot is stale; refresh get_usage_limits and save a new snapshot.")
        return 2

    remaining = min(float(quota["primaryRemaining"]), float(quota["weeklyRemaining"]))
    print(f"Quota preflight: snapshot age {age // 60}m; limiting window {remaining:g}% remaining.")
    if not args.execute:
        print("PREVIEW ONLY: no provider was launched and no model request was sent.")
        print(f"Would run a read-only review in {repo} on {', '.join(target_paths)} with providers: {', '.join(providers)}")
        print("MCO is an optional comparative review; it does not reduce Codex usage.")
        return 0

    if remaining <= MIN_REMAINING_PERCENT:
        print(f"DENIED: optional MCO review requires more than {MIN_REMAINING_PERCENT}% in both usage windows.")
        return 3
    if args.confirm_provider_team != args.providers:
        print("DENIED: confirm the exact provider team with the user, then repeat it with --confirm-provider-team.")
        return 4
    if not repo.is_dir():
        parser.error("--repo must point to an existing directory")
    if not args.prompt_file.is_file():
        parser.error("--prompt-file must point to an existing file")
    if args.prompt_file.stat().st_size > MAX_PROMPT_CHARS * 4:
        parser.error(f"prompt file is larger than the {MAX_PROMPT_CHARS}-character limit")
    try:
        prompt = args.prompt_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as exc:
        parser.error(f"cannot read prompt file: {exc}")
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        parser.error(f"prompt must contain 1–{MAX_PROMPT_CHARS} characters")

    executable = shutil.which("mco")
    if executable is None:
        parser.error("MCO CLI not found; install it only if you intend to use comparative review")

    command = build_command(executable, repo, providers, target_paths, prompt)
    print(f"Dispatching read-only MCO review to the confirmed providers: {', '.join(providers)}")
    try:
        return subprocess.run(command, check=False).returncode
    except OSError as exc:
        print(f"MCO could not be started: {exc}", file=sys.stderr)
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
