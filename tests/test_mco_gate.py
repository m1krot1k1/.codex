from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GATE = REPO / "scripts" / "mco_gate.py"
sys.path.insert(0, str(REPO / "scripts"))
from quota_snapshot import record_snapshot


class McoGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state" / "adaptive-quota.json"
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "src").mkdir()
        self.prompt = self.root / "prompt.md"
        self.prompt.write_text("Review only changed code for high-risk regressions.", encoding="utf-8")
        self.capture = self.root / "arguments.json"
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        self.fake_mco = bin_dir / "mco"
        self.fake_mco.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "open(os.environ['MCO_CAPTURE'], 'w').write(json.dumps(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        self.fake_mco.chmod(0o755)
        self.record_usage(weekly_used=20)

    def tearDown(self):
        self.temp.cleanup()

    def record_usage(self, *, weekly_used: float):
        now = int(time.time())
        record_snapshot(
            self.state,
            primary_used_percent=10,
            primary_resets_at=now + 3600,
            weekly_used_percent=weekly_used,
            weekly_resets_at=now + 86_400,
            captured_at=now,
        )

    def command(self, *extra: str) -> list[str]:
        return [
            sys.executable, str(GATE), "--snapshot", str(self.state),
            "--repo", str(self.repo), "--providers", "claude,codex",
            "--target-paths", "src", "--prompt-file", str(self.prompt), *extra,
        ]

    def env(self):
        return {**os.environ, "MCO_CAPTURE": str(self.capture), "PATH": f"{self.fake_mco.parent}{os.pathsep}{os.environ.get('PATH', '')}"}

    def test_preview_never_starts_a_provider(self):
        result = subprocess.run(self.command(), capture_output=True, text=True, env=self.env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no provider was launched", result.stdout)
        self.assertIn("on src", result.stdout)
        self.assertFalse(self.capture.exists())

    def test_low_weekly_reserve_blocks_even_explicit_execution(self):
        self.record_usage(weekly_used=80)
        result = subprocess.run(
            self.command("--execute", "--confirm-provider-team", "claude,codex"),
            capture_output=True,
            text=True,
            env=self.env(),
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("requires more than 50%", result.stdout)
        self.assertFalse(self.capture.exists())

    def test_unconfirmed_provider_team_blocks_execution(self):
        result = subprocess.run(self.command("--execute"), capture_output=True, text=True)
        self.assertEqual(result.returncode, 4)
        self.assertFalse(self.capture.exists())

    def test_confirmed_team_dispatches_read_only_with_explicit_providers(self):
        result = subprocess.run(
            self.command("--execute", "--confirm-provider-team", "claude,codex"),
            capture_output=True,
            text=True,
            env=self.env(),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.capture.read_text(encoding="utf-8"))
        self.assertIn("review", args)
        self.assertIn("claude,codex", args)
        self.assertIn("read_only", args)
        self.assertIn("strict", args)
        self.assertIn("300", args)
        self.assertIn("src", args)
        self.assertIn("--allow-paths", args)

    def test_missing_snapshot_blocks_execution(self):
        self.state.unlink()
        result = subprocess.run(self.command("--execute", "--confirm-provider-team", "claude,codex"), capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.capture.exists())

    def test_rejects_unbounded_or_outside_repository_scope(self):
        for target in (".", "../outside"):
            result = subprocess.run(
                [sys.executable, str(GATE), "--snapshot", str(self.state), "--repo", str(self.repo),
                 "--providers", "claude,codex", "--target-paths", target, "--prompt-file", str(self.prompt)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.capture.exists())

    def test_rejects_more_than_three_providers(self):
        result = subprocess.run(
            [sys.executable, str(GATE), "--snapshot", str(self.state), "--repo", str(self.repo),
             "--providers", "claude,codex,gemini,pi", "--target-paths", "src", "--prompt-file", str(self.prompt)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)

    def test_rejects_oversized_review_prompt(self):
        self.prompt.write_text("x" * 8001, encoding="utf-8")
        result = subprocess.run(self.command("--execute", "--confirm-provider-team", "claude,codex"), capture_output=True, text=True, env=self.env())
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.capture.exists())


if __name__ == "__main__":
    unittest.main()
