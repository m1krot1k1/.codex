---
name: mco-review
description: Use only when the user explicitly requests an independent multi-provider review or a genuinely high-risk change merits it. Requires a fresh usage snapshot and explicit confirmation of the provider team.
---

# Optional MCO comparative review

MCO launches separate provider CLIs and returns their raw answers. It does not save Codex usage and does not validate findings automatically. Read-only MCO review is the only supported route in this package; do not use MCO for parallel writes. MCO path restrictions validate the requested scope but are not an operating-system sandbox; actual sandbox strength depends on the provider CLI. The gate uses strict enforcement and should fail when the provider cannot meet the requested permission mode.

1. Confirm that an independent review is likely to change a consequential decision. Prefer Codex’s built-in review or targeted tests when they are enough.
2. Refresh `get_usage_limits` and the sanitized quota snapshot. Both windows must have **more than 50% remaining**. A missing/stale snapshot or a reserve breach blocks dispatch.
3. Choose only two or three provider IDs, name the exact team and model choices (if applicable) to the user, explain that each provider may use its own plan or API, and get explicit confirmation of that exact team before dispatch.
4. Choose explicit target files/directories inside the repository; whole-repository scope is blocked. Write a narrowly scoped prompt in a temporary file that excludes secrets and unrelated repository context. First preview without `--execute`:

   ```bash
   python3 "$CODEX_HOME/tools/adaptive-codex/mco_gate.py" \
     --repo /path/to/repo --providers claude,codex \
     --target-paths src/important-module,tests/important-module \
     --confirm-provider-team claude,codex \
     --prompt-file /path/to/review-prompt.txt
   ```

5. Only after the user's confirmation, repeat the command with `--execute`. The gate rechecks the fresh snapshot, path scope, and provider limit; it runs a strict read-only review with a five-minute global timeout. It never writes to the repository and never installs MCO.
6. Treat all findings as hypotheses; inspect the evidence in source and tests. Report disagreements and failed providers. Do not retry automatically.

Never bypass the gate because Codex CLI or another provider is directly available. The gate is an opt-in policy aid, not an account-wide quota enforcement mechanism.
