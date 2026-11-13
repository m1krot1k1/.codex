---
name: adaptive-codex
description: Use for multi-step coding, repository changes, debugging, tests, code review, or agent delegation in Codex. Chooses the smallest sufficient workflow and checks both usage windows and their reset times before costly phases.
---

# Adaptive Codex workflow

Use this workflow for development tasks. Follow the active project `AGENTS.md`; this skill does not override it.

## 1. Preflight before model work

1. Read applicable `AGENTS.md`, inspect the branch and dirty files, and keep existing user changes intact.
2. If `get_usage_limits` is available, read it at task start and before each new model-costly phase. Use the `codex` bucket from `rateLimitsByLimitId` when present; otherwise use the legacy bucket. Treat `usedPercent` as consumed, not remaining. Read both `primary` (short window) and `secondary` (weekly window) and both `resetsAt` timestamps.
3. Extract only the allowed fields and save a short-lived sanitized snapshot with the installed `quota_snapshot.py`:

   ```bash
   python3 "$CODEX_HOME/tools/adaptive-codex/quota_snapshot.py" record \
     --primary-used-percent 31 --primary-resets-at 1794149178 \
     --weekly-used-percent 79 --weekly-resets-at 1794157132 \
     --saved-reset-available
   ```

   Replace the example numbers with the current meter values. Never copy `accountId`, reset-credit IDs, auth data, or the raw tool response into files. The snapshot stores only percentages, reset timestamps, capture time, and a boolean that a reset is available. It expires after 15 minutes.
4. Ask the installed `quota_guard.py --snapshot "$CODEX_HOME/state/adaptive-quota.json"` for the current recommendation. If the usage meter is unavailable or the snapshot is missing/stale, use closed mode: Luna Medium, no Astra, Fast off, and at most one agent only when clearly valuable.

## 2. Pick the smallest workflow that can verify the result

- Small and clear task: coordinator alone.
- Medium task with unclear code ownership: at most one `repo_scout`, then one bounded `implementer` if the result materially helps.
- Complex, ambiguous, or cross-package task: ask `adaptive_architect` for an evidence-based plan first. The coordinator chooses boundaries before any implementation agents start.
- Assign non-overlapping file ownership. Avoid agents when the coordinator can do the task in less time or with fewer total model calls.
- Run the narrowest relevant checks. Use `test_fixer` only for a concrete failing command and error, with at most two repair attempts.
- Use `reviewer` only after checks when risk, diff size, or the user’s request warrants another paid model pass. Astra is a rare escalation, not a default tier.
- Keep long work resumable: leave the important decisions, files, checks, risks, and next action in the existing Codex thread. Do not create duplicate log files.

## 3. Respect both windows and the reset schedule

Use the short window to set the pace of current work and the weekly window as a planning horizon and reserve boundary. Refresh the meter after a costly phase. The meter is account-wide and can change in other chats or devices.

- Use the **short** window to choose the current model-work pace. At 50% or less short-window balance, remove optional review and Astra; at 35% or less, do not start new agent stages.
- A weekly balance at 10% or less does not block useful work when its reset is within 2 hours; route by the short-window balance and task value. If the user explicitly says to continue despite the weekly limit, pass `--user-authorized-continue` to the guard and route by the short window even if the reset is farther away.
- A low weekly balance above 10% does not by itself disable useful agent stages, Fast, or required checks. Keep using the current short-window headroom for worthwhile work; refresh both official readings before costly phases and account for the weekly reset as a shared boundary.
- At 25% or less in the **short** window, wait for its reset only when the short-window balance is low, the reset is near, and the specific task can wait.
- At 10% or less in the **short** window: stop new costly stages unless the user explicitly directs continuation; even then, use short-window routing and do not bypass the platform's actual limit.
- A near weekly reset does not itself require pausing useful work. Use it in the schedule, while selecting stages from short-window headroom and task value; do not spend quota merely to empty the short-window meter.
- At 100%, budget for the full time to the weekly reset. Even pacing is only a rough reserve cue, not a prediction of task cost. Keep Luna Medium as default, and preserve allowance for other chats/devices.
- If a saved free reset is shown, tell the user only when it could avoid waiting. Never consume it or imply availability bypasses current eligibility; the user decides.

## 4. Fast and comparative tools

- Fast is a separate Codex speed setting that uses more allowance. Keep it off by default. Only consider it for an urgent bounded step when the fresh short-window balance is above 50% and the time saved matters; a weekly reset within 2 hours or the user's explicit weekly override can satisfy the weekly gate. Ask the user to toggle it in the app if no supported UI control is available; remind them to turn it off afterward. Never infer an exact cost multiplier from the UI label.
- MCO is an optional independent review, not an economy mode. It launches additional provider calls and may consume the same Plus allowance when `codex` is selected. Do not call MCO by default. For a genuinely high-risk review, require a fresh snapshot, more than 50% in both windows, a provider team explicitly chosen and confirmed with the user, and read-only review. Use `mco_gate.py`; do not invoke raw MCO commands around the gate.
- No local model/provider is configured by this package.

## 5. Verify and report

Inspect the actual diff after delegated work. Run only the requested or directly relevant checks. Report what changed, the checks and their result, remaining uncertainty, and any next step that needs the user. Never promise no bugs or no quota exhaustion.
