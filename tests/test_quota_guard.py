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

    def test_low_weekly_reserve_does_not_reduce_short_window_route(self):
        plan = quota_guard.make_plan(62, 1.5, 24, 6)
        self.assertEqual(plan["state"], "balanced")
        self.assertEqual(plan["fast"], "off")
        self.assertEqual(plan["max_concurrent_agents"], 2)
        self.assertTrue(any("сам по себе не сокращает число агентов" in reason for reason in plan["reasons"]))

    def test_continue_flag_does_not_change_low_weekly_route(self):
        plan = quota_guard.make_plan(62, 1.5, 24, 6, user_authorized_continue=True)
        self.assertEqual(plan["state"], "balanced")
        self.assertEqual(plan["model"], "gpt-6-luna")
        self.assertEqual(plan["fast"], "off")
        self.assertEqual(plan["max_concurrent_agents"], 2)

    def test_saved_reset_is_not_redeemed_automatically(self):
        plan = quota_guard.make_plan(62, 1.5, 8, 6, saved_reset_available=True)
        self.assertEqual(plan["state"], "stop")
        self.assertTrue(any("не применять без явного решения" in reason for reason in plan["reasons"]))

    def test_short_window_headroom_is_used_even_when_weekly_is_low_and_reset_is_near(self):
        plan = quota_guard.make_plan(91, 3.9, 18, 6.7)
        self.assertEqual(plan["state"], "balanced")
        self.assertEqual(plan["model"], "gpt-6-luna")
        self.assertEqual(plan["fast"], "off")
        self.assertEqual(plan["max_concurrent_agents"], 2)
        self.assertTrue(any("сам по себе не сокращает число агентов" in reason for reason in plan["reasons"]))

    def test_near_low_weekly_reset_does_not_auto_pause(self):
        plan = quota_guard.make_plan(58, 3, 24, 0.5)
        self.assertEqual(plan["state"], "balanced")
        self.assertEqual(plan["max_concurrent_agents"], 2)

    def test_very_low_window_stops_unless_user_explicitly_continues(self):
        plan = quota_guard.make_plan(91, 3.9, 8, 6.7)
        self.assertEqual(plan["state"], "stop")
        continued = quota_guard.make_plan(91, 3.9, 8, 6.7, user_authorized_continue=True)
        self.assertEqual(continued["state"], "balanced")
        self.assertEqual(continued["max_concurrent_agents"], 2)

    def test_near_weekly_reset_below_ten_uses_available_short_window(self):
        plan = quota_guard.make_plan(92, 1.5, 9, 1.5, urgent=True)
        self.assertEqual(plan["state"], "balanced")
        self.assertEqual(plan["max_concurrent_agents"], 2)
        self.assertEqual(plan["fast"], "eligible_for_manual_consideration")
        self.assertTrue(any("сброс будет в течение 2 часов" in reason for reason in plan["reasons"]))

    def test_far_weekly_floor_stops_without_explicit_user_override(self):
        plan = quota_guard.make_plan(92, 1.5, 9, 6)
        self.assertEqual(plan["state"], "stop")

    def test_explicit_weekly_override_allows_short_window_and_fast_candidate(self):
        plan = quota_guard.make_plan(92, 1.5, 9, 6, urgent=True, user_authorized_continue=True)
        self.assertEqual(plan["state"], "balanced")
        self.assertEqual(plan["max_concurrent_agents"], 2)
        self.assertEqual(plan["fast"], "eligible_for_manual_consideration")

    def test_near_weekly_reset_does_not_override_low_short_window(self):
        plan = quota_guard.make_plan(8, 1.5, 9, 1.5)
        self.assertEqual(plan["state"], "stop")

    def test_low_short_window_limits_agents_even_when_weekly_is_full(self):
        plan = quota_guard.make_plan(30, 2, 95, 72)
        self.assertEqual(plan["state"], "conserve")
        self.assertEqual(plan["max_concurrent_agents"], 0)

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

    def test_low_weekly_usage_does_not_block_fast_when_short_window_is_available(self):
        plan = quota_guard.make_plan(80, 2, 42, 72, urgent=True)
        self.assertEqual(plan["fast"], "eligible_for_manual_consideration")
        self.assertEqual(plan["max_concurrent_agents"], 2)

    def test_low_weekly_usage_does_not_block_critical_model_with_user_authorization(self):
        plan = quota_guard.make_plan(90, 4, 18, 6, critical=True, sol_authorized=True)
        self.assertEqual(plan["model"], "gpt-6.1-sol")
        self.assertEqual(plan["max_concurrent_agents"], 2)

    def test_near_short_reset_waits_when_window_is_low(self):
        plan = quota_guard.make_plan(20, 0.5, 90, 48)
        self.assertEqual(plan["state"], "wait_for_reset")

    def test_explicit_continue_uses_short_window_even_when_it_is_low(self):
        plan = quota_guard.make_plan(8, 0.5, 90, 48, user_authorized_continue=True)
        self.assertEqual(plan["state"], "conserve")
        self.assertEqual(plan["max_concurrent_agents"], 0)
        self.assertEqual(plan["fast"], "off")


if __name__ == "__main__":
    unittest.main()
