from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "quota_snapshot.py"
SPEC = importlib.util.spec_from_file_location("quota_snapshot", SCRIPT)
quota_snapshot = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = quota_snapshot
SPEC.loader.exec_module(quota_snapshot)


class QuotaSnapshotTests(unittest.TestCase):
    def record(self, path: Path, *, captured_at: int = 1_700_000_000) -> dict:
        return quota_snapshot.record_snapshot(
            path,
            primary_used_percent=31,
            primary_resets_at=1_700_010_000,
            weekly_used_percent=79,
            weekly_resets_at=1_700_020_000,
            saved_reset_available=True,
            captured_at=captured_at,
        )

    def test_snapshot_is_sanitized_private_and_fresh(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state" / "adaptive-quota.json"
            data = self.record(path)
            self.assertEqual(set(data), {
                "schemaVersion", "capturedAt", "primaryRemaining", "primaryResetsAt",
                "weeklyRemaining", "weeklyResetsAt", "savedResetAvailable", "savedResetExpiresAt",
            })
            self.assertNotIn("accountId", path.read_text())
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            stored, fresh, age = quota_snapshot.read_snapshot(path, now=1_700_000_300)
            self.assertEqual(stored["weeklyRemaining"], 21)
            self.assertTrue(fresh)
            self.assertEqual(age, 300)

    def test_expired_future_or_malformed_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "snapshot.json"
            self.record(path)
            self.assertEqual(quota_snapshot.read_snapshot(path, now=1_700_001_000)[1], False)
            self.assertEqual(quota_snapshot.read_snapshot(path, now=1_699_999_000)[0], None)
            path.write_text(json.dumps({"schemaVersion": 1, "capturedAt": 1}), encoding="utf-8")
            self.assertEqual(quota_snapshot.read_snapshot(path)[0], None)

    def test_invalid_percentages_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                quota_snapshot.record_snapshot(
                    Path(temp) / "snapshot.json",
                    primary_used_percent=101,
                    primary_resets_at=1_700_010_000,
                    weekly_used_percent=0,
                    weekly_resets_at=1_700_020_000,
                )

    def test_quota_guard_uses_fresh_snapshot_and_fails_closed_when_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "snapshot.json"
            now = int(time.time())
            quota_snapshot.record_snapshot(
                path,
                primary_used_percent=38,
                primary_resets_at=now + 10_000,
                weekly_used_percent=76,
                weekly_resets_at=now + 30_000,
                captured_at=now,
            )
            script = SCRIPT.parent / "quota_guard.py"
            fresh = subprocess.run([sys.executable, str(script), "--snapshot", str(path)], capture_output=True, text=True, check=True)
            self.assertIn("Недельный остаток", fresh.stdout)
            self.assertIn("Fast: off", fresh.stdout)
            quota_snapshot.record_snapshot(
                path,
                primary_used_percent=38,
                primary_resets_at=now + 10_000,
                weekly_used_percent=76,
                weekly_resets_at=now + 30_000,
                captured_at=now - 3600,
            )
            stale = subprocess.run([sys.executable, str(script), "--snapshot", str(path)], capture_output=True, text=True, check=True)
            self.assertIn("Состояние: unknown", stale.stdout)
            self.assertIn("без необязательных этапов", stale.stdout)


if __name__ == "__main__":
    unittest.main()
