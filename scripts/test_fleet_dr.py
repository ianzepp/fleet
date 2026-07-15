from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parent / "fleet-sensors.py"
spec = importlib.util.spec_from_file_location("fleet_sensors", SCRIPT)
fleet_sensors = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(fleet_sensors)

NOW = datetime(2026, 7, 15, tzinfo=timezone.utc)


def iso(date):
    return date.replace(tzinfo=timezone.utc).isoformat()


class DisasterRecoveryCadenceTests(unittest.TestCase):
    def evaluate(self, fleet, baseline=None, posture="growth", tasks=None):
        return fleet_sensors.evaluate_disaster_recovery(fleet, baseline or {}, posture, NOW, tasks or [])

    def test_missing_off_disabled_policy_is_silent(self):
        for policy in (None, {"enabled": False, "tier": "critical"}, {"enabled": True, "tier": "off"}):
            fleet = {} if policy is None else {"disaster_recovery": policy}
            state, signals = self.evaluate(fleet)
            self.assertIsNone(state)
            self.assertEqual(signals, [])

    def test_tier_defaults(self):
        expected = {
            "inventory": (30, 90, None),
            "critical": (14, 60, 180),
            "regulated_or_irreplaceable": (7, 30, 90),
        }
        for tier, values in expected.items():
            policy = fleet_sensors.disaster_recovery_policy({"disaster_recovery": {"enabled": True, "tier": tier}})
            self.assertEqual((policy["freshness_check_days"], policy["analysis_days"], policy["restore_drill_days"]), values)
            self.assertEqual(policy["grace_days"], 7)

    def test_no_receipts_causes_analysis_due_first(self):
        state, signals = self.evaluate({"disaster_recovery": {"enabled": True, "tier": "critical"}})
        self.assertFalse(state["due"]["freshness"]["due"])
        self.assertTrue(state["due"]["analysis"]["due"])
        self.assertFalse(state["due"]["restore_drill"]["due"])
        self.assertEqual(signals, ["head_due_coo_dr_analysis"])

    def test_freshness_boundary_29_vs_31_days(self):
        fleet = {"disaster_recovery": {"enabled": True, "tier": "inventory"}}
        base = {"disaster_recovery": {"last_freshness_check_at": iso(datetime(2026, 6, 16)), "last_analysis_at": iso(datetime(2026, 7, 1))}}
        state, _ = self.evaluate(fleet, base)
        self.assertEqual(state["due"]["freshness"]["days_since"], 29)
        self.assertFalse(state["due"]["freshness"]["due"])
        base["disaster_recovery"]["last_freshness_check_at"] = iso(datetime(2026, 6, 14))
        state, signals = self.evaluate(fleet, base)
        self.assertEqual(state["due"]["freshness"]["days_since"], 31)
        self.assertTrue(state["due"]["freshness"]["due"])
        self.assertIn("head_due_coo_dr_freshness", signals)

    def test_due_within_grace_vs_overdue_exact_days(self):
        fleet = {"disaster_recovery": {"enabled": True, "tier": "inventory", "grace_days": 7}}
        base = {"disaster_recovery": {"last_freshness_check_at": iso(datetime(2026, 6, 8)), "last_analysis_at": iso(datetime(2026, 7, 1))}}
        state, signals = self.evaluate(fleet, base)
        self.assertEqual(state["due"]["freshness"]["days_overdue"], 7)
        self.assertTrue(state["due"]["freshness"]["due"])
        self.assertFalse(state["due"]["freshness"]["overdue"])
        self.assertNotIn("head_overdue_coo_dr_freshness", signals)
        base["disaster_recovery"]["last_freshness_check_at"] = iso(datetime(2026, 6, 7))
        state, signals = self.evaluate(fleet, base)
        self.assertEqual(state["due"]["freshness"]["days_overdue"], 8)
        self.assertTrue(state["due"]["freshness"]["overdue"])
        self.assertIn("head_overdue_coo_dr_freshness", signals)

    def test_null_restore_cadence_yields_no_restore_due(self):
        fleet = {"disaster_recovery": {"enabled": True, "tier": "inventory"}}
        base = {"disaster_recovery": {"last_freshness_check_at": iso(datetime(2026, 7, 1)), "last_analysis_at": iso(datetime(2026, 7, 1))}}
        state, signals = self.evaluate(fleet, base)
        self.assertFalse(state["due"]["restore_drill"]["applicable"])
        self.assertNotIn("head_due_coo_dr_restore_drill", signals)

    def test_backup_freshness_never_sets_restore_tested_or_remote_coverage(self):
        fleet = {"disaster_recovery": {"enabled": True, "tier": "critical"}}
        base = {"disaster_recovery": {"last_freshness_check_at": iso(datetime(2026, 7, 1)), "last_analysis_at": iso(datetime(2026, 7, 1)), "git_remote_count": 1}}
        state, _ = self.evaluate(fleet, base)
        self.assertFalse(state["receipts"]["restore_tested"])
        self.assertNotIn("git_remote_count", state["receipts"])
        self.assertIn("remote_is_not_restore_proof", state["false_assurance_bans"])

    def test_dormant_critical_visible_paused_but_off_silent(self):
        critical = {"disaster_recovery": {"enabled": True, "tier": "critical"}}
        state, signals = self.evaluate(critical, posture="dormant")
        self.assertTrue(state["assignment"]["paused_by_posture"])
        self.assertIn("head_due_coo_dr_analysis", signals)
        off_state, off_signals = self.evaluate({"disaster_recovery": {"enabled": True, "tier": "off"}}, posture="dormant")
        self.assertIsNone(off_state)
        self.assertEqual(off_signals, [])

    def test_outstanding_coo_dr_assignment_suppresses_duplicate_recommendation(self):
        fleet = {"disaster_recovery": {"enabled": True, "tier": "critical"}}
        state, signals = self.evaluate(fleet, tasks=[{"handle": "abc123", "subject": "COO disaster recovery analysis"}])
        self.assertTrue(state["assignment"]["outstanding"])
        self.assertTrue(state["assignment"]["duplicate_suppressed"])
        self.assertIn("head_due_coo_dr_analysis", signals)

    def test_malformed_timestamp_and_config_report_unknown_without_crash(self):
        fleet = {"disaster_recovery": {"enabled": True, "tier": "critical"}}
        state, signals = self.evaluate(fleet, {"disaster_recovery": {"last_analysis_at": "not-a-date"}})
        self.assertEqual(state["status"], "unknown")
        self.assertIn("coo_dr_receipt_unknown", signals)
        bad_state, bad_signals = self.evaluate({"disaster_recovery": {"enabled": True, "tier": "critical", "analysis_days": "soon"}})
        self.assertEqual(bad_state["status"], "unknown")
        self.assertIn("head_due_coo_dr_analysis", bad_signals)

    def test_string_enabled_and_missing_tier_fail_visible_not_enabled(self):
        string_state, string_signals = self.evaluate({"disaster_recovery": {"enabled": "false", "tier": "critical"}})
        self.assertEqual(string_state["status"], "unknown")
        self.assertIn("enabled must be boolean", string_state["error"])
        self.assertIn("head_due_coo_dr_analysis", string_signals)

        missing_state, missing_signals = self.evaluate({"disaster_recovery": {"enabled": True}})
        self.assertEqual(missing_state["status"], "unknown")
        self.assertIn("tier is required", missing_state["error"])
        self.assertIn("head_due_coo_dr_analysis", missing_signals)

        typed_state, typed_signals = self.evaluate({"disaster_recovery": {"enabled": True, "tier": 1}})
        self.assertEqual(typed_state["status"], "unknown")
        self.assertIn("tier must be a string", typed_state["error"])
        self.assertIn("head_due_coo_dr_analysis", typed_signals)

    def test_string_and_float_cadence_fail_visible(self):
        for field, value in (("freshness_check_days", "30"), ("analysis_days", 30.5), ("restore_drill_days", 90.0), ("grace_days", "7")):
            state, signals = self.evaluate({"disaster_recovery": {"enabled": True, "tier": "critical", field: value}})
            self.assertEqual(state["status"], "unknown")
            self.assertIn(field, state["error"])
            self.assertIn("head_due_coo_dr_analysis", signals)

    def test_future_receipt_timestamp_reports_unknown(self):
        fleet = {"disaster_recovery": {"enabled": True, "tier": "critical"}}
        state, signals = self.evaluate(fleet, {"disaster_recovery": {"last_analysis_at": iso(datetime(2026, 7, 16))}})
        self.assertEqual(state["status"], "unknown")
        self.assertIn("future last_analysis_at", state["errors"])
        self.assertIn("coo_dr_receipt_unknown", signals)
        self.assertIn("head_due_coo_dr_analysis", signals)


if __name__ == "__main__":
    unittest.main()
