#!/usr/bin/env python3
import importlib.util
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def load_sensors():
    path = SCRIPTS / "fleet-sensors.py"
    spec = importlib.util.spec_from_file_location("fleet_sensors", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


sensors = load_sensors()


class LaneLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)

    def observe(self, previous=None, **overrides):
        values = {
            "previous": previous or {},
            "signature": "same",
            "now": self.now,
            "stale_after_cycles": 5,
            "resume_stale_after_hours": 24,
            "runtime_state": "waiting_for_input",
            "has_open_work": True,
            "intentionally_parked": False,
        }
        values.update(overrides)
        return sensors.lane_progress_observation(**values)

    def test_binding_accepts_lane_and_legacy_packet(self):
        self.assertEqual(
            sensors.lane_binding({"lane": {"campaign": "docs/CAMPAIGN.md"}}),
            {"campaign": "docs/CAMPAIGN.md", "binding_kind": "lane"},
        )
        self.assertEqual(
            sensors.lane_binding({"packet": {"slug": "parser"}}),
            {"slug": "parser", "binding_kind": "packet"},
        )
        self.assertIsNone(sensors.lane_binding({}))

    def test_signature_tracks_board_and_git_progress(self):
        binding = {"binding_kind": "lane", "campaign": "docs/CAMPAIGN.md"}
        original = sensors.lane_progress_signature(
            binding,
            [{"handle": "aaaaaa"}],
            [],
            None,
            {"available": True, "head": "one", "dirty": False},
        )
        task_changed = sensors.lane_progress_signature(
            binding,
            [{"handle": "bbbbbb"}],
            [],
            None,
            {"available": True, "head": "one", "dirty": False},
        )
        git_changed = sensors.lane_progress_signature(
            binding,
            [{"handle": "aaaaaa"}],
            [],
            None,
            {"available": True, "head": "two", "dirty": False},
        )
        self.assertNotEqual(original, task_changed)
        self.assertNotEqual(original, git_changed)

    def test_remote_git_is_explicitly_unavailable(self):
        self.assertEqual(
            sensors.lane_git_state("/not/inspected", remote=True),
            {"available": False, "reason": "remote"},
        )

    def test_candidate_after_five_unchanged_cycles(self):
        previous = {"signature": "same", "unchanged_cycles": 4, "last_progress_at": self.now.isoformat()}
        result = self.observe(previous)
        self.assertTrue(result["candidate"])
        self.assertEqual(result["reason"], "stale_bound")

    def test_empty_retained_lane_has_distinct_reason(self):
        previous = {"signature": "same", "unchanged_cycles": 4, "last_progress_at": self.now.isoformat()}
        result = self.observe(previous, has_open_work=False)
        self.assertEqual(result["reason"], "empty_retained")

    def test_progress_resets_candidate_age(self):
        previous = {"signature": "old", "unchanged_cycles": 20, "last_progress_at": self.now.isoformat()}
        result = self.observe(previous)
        self.assertFalse(result["candidate"])
        self.assertEqual(result["unchanged_cycles"], 0)

    def test_intentional_park_suppresses_candidate(self):
        previous = {"signature": "same", "unchanged_cycles": 20, "last_progress_at": self.now.isoformat()}
        result = self.observe(previous, intentionally_parked=True)
        self.assertFalse(result["candidate"])

    def test_running_lane_is_not_candidate(self):
        previous = {"signature": "same", "unchanged_cycles": 20, "last_progress_at": self.now.isoformat()}
        result = self.observe(previous, runtime_state="running")
        self.assertFalse(result["candidate"])

    def test_offline_age_surfaces_resume_candidate(self):
        previous = {
            "signature": "same",
            "unchanged_cycles": 1,
            "last_progress_at": (self.now - timedelta(hours=25)).isoformat(),
        }
        result = self.observe(previous, runtime_state="stopped")
        self.assertTrue(result["candidate"])
        self.assertEqual(result["reason"], "resume_stale")


if __name__ == "__main__":
    unittest.main()
