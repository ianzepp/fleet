#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def load_validator():
    path = SCRIPTS / "verify-fleet-json.py"
    spec = importlib.util.spec_from_file_location("verify_fleet_json", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


validator = load_validator()


class AuditorHandValidationTest(unittest.TestCase):
    def validate(self, auditor):
        fleet = {"fleet_id": "test", "hands": {"auditor-1": auditor}}
        return validator.validate(fleet, Path("/tmp/.vivi/fleet.json"), path_checks=False)

    def valid_auditor(self):
        return {
            "mail_identity": "auditor-1",
            "tmux_target": "test:auditor-1.1",
            "merges_to_main": False,
            "assignment_mode": "new",
        }

    def test_accepts_canonical_auditor_hand(self):
        report = self.validate(self.valid_auditor())
        self.assertEqual(report.errors, [])

    def test_rejects_auditor_that_can_merge(self):
        auditor = self.valid_auditor()
        auditor["merges_to_main"] = True
        report = self.validate(auditor)
        self.assertIn(
            ("hands.auditor-1", "auditor Hand requires merges_to_main=false"),
            report.errors,
        )

    def test_rejects_missing_fresh_assignment_mode(self):
        auditor = self.valid_auditor()
        auditor.pop("assignment_mode")
        report = self.validate(auditor)
        self.assertIn(
            ("hands.auditor-1", "auditor Hand requires assignment_mode='new' for independent review"),
            report.errors,
        )

    def test_rejects_mismatched_auditor_identity(self):
        auditor = self.valid_auditor()
        auditor["mail_identity"] = "hand-2"
        report = self.validate(auditor)
        self.assertIn(
            ("hands.auditor-1", "auditor mail_identity must match role name 'auditor-1'"),
            report.errors,
        )

    def test_rejects_malformed_auditor_role_name(self):
        auditor = self.valid_auditor()
        fleet = {"fleet_id": "test", "hands": {"auditor-zero": auditor}}
        report = validator.validate(fleet, Path("/tmp/.vivi/fleet.json"), path_checks=False)
        self.assertIn(
            ("hands.auditor-zero", "auditor Hand name must match auditor-N with N >= 1"),
            report.errors,
        )


class LaneLifecycleValidationTest(unittest.TestCase):
    def validate(self, policy):
        fleet = {"fleet_id": "test", "hands": {}, "lane_lifecycle": policy}
        return validator.validate(fleet, Path("/tmp/.vivi/fleet.json"), path_checks=False)

    def test_accepts_canonical_lane_policy(self):
        report = self.validate({
            "stale_after_cycles": 5,
            "resume_stale_after_hours": 24,
            "release_grace_cycles": 2,
            "worktree_cleanup": "manual",
        })
        self.assertEqual(report.errors, [])

    def test_rejects_automatic_worktree_cleanup(self):
        report = self.validate({"worktree_cleanup": "automatic"})
        self.assertIn(
            (
                "$.lane_lifecycle.worktree_cleanup",
                "must be 'manual'; lane release never deletes worktrees",
            ),
            report.errors,
        )

    def test_rejects_invalid_lane_thresholds(self):
        report = self.validate({
            "stale_after_cycles": 0,
            "resume_stale_after_hours": -1,
            "release_grace_cycles": -1,
        })
        self.assertEqual(len(report.errors), 3)

    def test_warns_when_parked_lane_has_no_wake_trigger(self):
        fleet = {
            "fleet_id": "test",
            "hands": {
                "hand-2": {
                    "mail_identity": "hand-2",
                    "tmux_target": "test:hand-2.1",
                    "lane": {"state": "parked", "campaign": "docs/CAMPAIGN.md"},
                }
            },
        }
        report = validator.validate(fleet, Path("/tmp/.vivi/fleet.json"), path_checks=False)
        self.assertIn(
            (
                "hands.hand-2.lane",
                "parked/deferred/blocked lane needs a wake trigger or remains a reconciliation candidate",
            ),
            report.warnings,
        )


if __name__ == "__main__":
    unittest.main()
