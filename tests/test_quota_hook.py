from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "plugins" / "adaptive-quota" / "hooks" / "session_start.py"


class QuotaHookTests(unittest.TestCase):
    def run_hook(self, home: Path) -> dict:
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            capture_output=True,
            text=True,
            env={**os.environ, "CODEX_HOME": str(home)},
            check=True,
        )
        return json.loads(result.stdout)

    def test_hook_injects_only_sanitized_fresh_usage_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            state = home / "state" / "adaptive-quota.json"
            state.parent.mkdir()
            now = int(time.time())
            state.write_text(json.dumps({
                "schemaVersion": 1,
                "capturedAt": now,
                "primaryRemaining": 69,
                "primaryResetsAt": now + 3600,
                "weeklyRemaining": 21,
                "weeklyResetsAt": now + 28800,
                "savedResetAvailable": True,
                "accountId": "must-not-be-read-or-output",
            }), encoding="utf-8")
            output = self.run_hook(home)
            context = output["hookSpecificOutput"]["additionalContext"]
            self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
            self.assertIn("short window 69%", context)
            self.assertIn("weekly window 21%", context)
            self.assertIn("never apply it automatically", context)
            self.assertNotIn("must-not-be-read-or-output", context)

    def test_hook_fails_closed_for_missing_or_stale_state(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            output = self.run_hook(home)
            context = output["hookSpecificOutput"]["additionalContext"]
            self.assertIn("missing, stale, or invalid", context)
            state = home / "state" / "adaptive-quota.json"
            state.parent.mkdir()
            state.write_text(json.dumps({
                "schemaVersion": 1,
                "capturedAt": int(time.time()) - 3600,
                "primaryRemaining": 100,
                "primaryResetsAt": int(time.time()) + 1000,
                "weeklyRemaining": 100,
                "weeklyResetsAt": int(time.time()) + 5000,
            }), encoding="utf-8")
            self.assertIn("missing, stale, or invalid", self.run_hook(home)["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
