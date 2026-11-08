from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "quota_guard.py"
SPEC = importlib.util.spec_from_file_location("quota_guard", SCRIPT)
quota_guard = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = quota_guard
SPEC.loader.exec_module(quota_guard)


class QuotaGuardTests(unittest.TestCase):
    def test_duration_parser(self):
        self.assertAlmostEqual(quota_guard.parse_duration("1h4m"), 64 / 60)
        self.assertAlmostEqual(quota_guard.parse_duration("8h17m"), 8 + 17 / 60)
        self.assertEqual(quota_guard.parse_duration("2d"), 48)

    def test_unknown_quota_fails_closed(self):
        plan = quota_guard.make_plan(None, None, None, None)
        self.assertEqual(plan["state"], "unknown")
        self.assertEqual(plan["model"], "gpt-6-luna")
        self.assertEqual(plan["fast"], "off")
        self.assertEqual(plan["max_concurrent_agents"], 1)

    def test_weekly_reserve_pauses_by_default(self):
        plan = quota_guard.make_plan(62, 1.5, 24, 6)
        self.assertEqual(plan["state"], "pause")
        self.assertEqual(plan["fast"], "off")

    def test_explicit_continue_at_low_weekly_budget_stays_solo(self):
        plan = quota_guard.make_plan(62, 1.5, 24, 6, user_authorized_continue=True)
        self.assertEqual(plan["state"], "conserve")
        self.assertEqual(plan["model"], "gpt-6-luna")
        self.assertEqual(plan["fast"], "off")
        self.assertEqual(plan["max_concurrent_agents"], 0)

    def test_saved_reset_is_not_redeemed_automatically(self):
        plan = quota_guard.make_plan(62, 1.5, 24, 6, saved_reset_available=True)
        self.assertEqual(plan["state"], "pause")
        self.assertTrue(any("спросить пользователя перед применением" in reason for reason in plan["reasons"]))

    def test_full_budget_does_not_enable_fast_without_urgency(self):
        plan = quota_guard.make_plan(100, 5, 100, 120)
        self.assertEqual(plan["state"], "balanced")
        self.assertEqual(plan["model"], "gpt-6-luna")
        self.assertEqual(plan["fast"], "off")
        self.assertIsNotNone(plan["weekly_even_pace_pp_per_day"])

    def test_fast_is_only_a_manual_candidate_for_urgent_work_with_headroom(self):
        plan = quota_guard.make_plan(80, 2, 90, 48, urgent=True)
        self.assertEqual(plan["fast"], "eligible_for_manual_consideration")
        self.assertEqual(plan["model"], "gpt-6-luna")

    def test_critical_model_escalation_does_not_enable_fast(self):
        plan = quota_guard.make_plan(100, 4, 100, 168, critical=True, sol_authorized=True)
        self.assertEqual(plan["model"], "gpt-6.1-sol")
        self.assertEqual(plan["reasoning"], "high")
        self.assertEqual(plan["fast"], "off")

    def test_critical_without_user_quota_confirmation_stays_on_luna(self):
        plan = quota_guard.make_plan(100, 4, 100, 168, critical=True)
        self.assertEqual(plan["model"], "gpt-6-luna")

    def test_urgent_work_with_low_weekly_usage_does_not_enable_fast(self):
        plan = quota_guard.make_plan(80, 2, 42, 72, urgent=True)
        self.assertEqual(plan["fast"], "off")

    def test_near_short_reset_waits_when_window_is_low(self):
        plan = quota_guard.make_plan(20, 0.5, 90, 48)
        self.assertEqual(plan["state"], "wait_for_reset")


if __name__ == "__main__":
    unittest.main()
