from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
import importlib.util
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
INSTALLER = REPO / "scripts" / "install.py"
spec = importlib.util.spec_from_file_location("adaptive_installer", INSTALLER)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


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

    def test_failed_write_restores_existing_files_and_removes_new_files(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            old = home / "existing"
            new = home / "new"
            old.write_text("original")
            original_write = installer.atomic_write
            calls = 0

            def fail_once(path, content, mode=None):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError("simulated failure")
                original_write(path, content, mode)

            with mock.patch.object(installer, "atomic_write", side_effect=fail_once):
                with self.assertRaisesRegex(OSError, "completed writes rolled back"):
                    installer.install_changes(home, {old: b"changed", new: b"new", home / "failure": b"x"})
            self.assertEqual(old.read_text(), "original")
            self.assertFalse(new.exists())
            backups = list((home / "backups" / "adaptive-codex-install").glob("*/existing"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "original")

    def test_backups_do_not_collide_on_repeated_installs(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            target = home / "existing"
            target.write_text("first")
            first = installer.install_changes(home, {target: b"second"})
            second = installer.install_changes(home, {target: b"third"})
            self.assertNotEqual(first, second)
            self.assertEqual((first / "existing").read_text(), "first")
            self.assertEqual((second / "existing").read_text(), "second")


if __name__ == "__main__":
    unittest.main()
