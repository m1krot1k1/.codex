from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "scripts" / "install.py"


class InstallerTests(unittest.TestCase):
    def test_install_merges_only_managed_settings_and_backs_up(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / ".codex"
            home.mkdir()
            (home / "AGENTS.md").write_text("# User instruction\n")
            original_config = (
                'model = "gpt-6-luna"\n'
                '\n[agents]\n'
                'enabled = false\n'
                'max_concurrent_threads_per_session = 7\n'
                'custom_note = "keep me"\n'
                '\n[profiles.personal]\nmodel = "gpt-6-astra"\n'
            )
            (home / "config.toml").write_text(original_config)
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--home", str(home)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Backups:", result.stdout)
            config = tomllib.loads((home / "config.toml").read_text())
            self.assertEqual(config["model"], "gpt-6-luna")
            self.assertEqual(config["profiles"]["personal"]["model"], "gpt-6-astra")
            self.assertEqual(config["agents"]["custom_note"], "keep me")
            self.assertEqual(config["agents"]["enabled"], True)
            self.assertEqual(config["agents"]["max_concurrent_threads_per_session"], 2)
            self.assertEqual((home / "AGENTS.md").read_text(), (REPO / "AGENTS.md").read_text())
            self.assertEqual((home / "skills" / "adaptive-codex" / "SKILL.md").read_bytes(), (REPO / "skills" / "adaptive-codex" / "SKILL.md").read_bytes())
            self.assertEqual((home / "tools" / "adaptive-codex" / "mco_gate.py").read_bytes(), (REPO / "scripts" / "mco_gate.py").read_bytes())
            self.assertTrue((home / "skills" / "mco-review" / "SKILL.md").is_file())
            self.assertTrue((home / "skills" / "codex-app-server" / "SKILL.md").is_file())
            backups = list((home / "backups" / "adaptive-codex-install").glob("*/"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "config.toml").read_text(), original_config)
            self.assertEqual((backups[0] / "AGENTS.md").read_text(), "# User instruction\n")

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / ".codex"
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--home", str(home), "--dry-run"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Would update:", result.stdout)
            self.assertFalse(home.exists())

    def test_repeat_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / ".codex"
            command = [sys.executable, str(INSTALLER), "--home", str(home)]
            subprocess.run(command, check=True, capture_output=True, text=True)
            second = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertIn("Already up to date", second.stdout)
            self.assertFalse((home / "backups").exists())


if __name__ == "__main__":
    unittest.main()
