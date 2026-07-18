#!/usr/bin/env python3
"""Focused tests for terminal runtime classification."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("fleet-sensors.py")
SPEC = importlib.util.spec_from_file_location("fleet_sensors", SCRIPT)
assert SPEC and SPEC.loader
fleet_sensors = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fleet_sensors)


class TerminalClassificationTests(unittest.TestCase):
    def test_kimi_idle(self) -> None:
        tail = """
Welcome to Kimi Code!
│ >  │
K3 thinking: low  /tmp/project  context: 0% (0/256k)
"""
        self.assertEqual(fleet_sensors.classify_terminal(tail, True), "waiting_for_input")

    def test_kimi_running(self) -> None:
        tail = """
✨ Inspect the project.
🌕 · Tip: @: mention files
│ >  │
K3 thinking: low  /tmp/project  context: 9% (22.5k/256k)
"""
        self.assertEqual(fleet_sensors.classify_terminal(tail, True), "running")

    def test_kimi_approval(self) -> None:
        tail = """
▶ Write this file?
1. Approve once
2. Approve for this session
3. Reject
4. Reject with feedback
↑/↓ select · 1/2/3/4 choose · ↵ confirm
"""
        self.assertEqual(fleet_sensors.classify_terminal(tail, True), "approval_required")

    def test_bare_shell_stays_unknown(self) -> None:
        self.assertEqual(fleet_sensors.classify_terminal("% ", True), "unknown")

    def test_stale_kimi_chrome_above_shell_is_not_ready(self) -> None:
        tail = """
Welcome to Kimi Code!
│ >  │
K3 thinking: low  context: 0% (0/256k)
exited
%
"""
        self.assertEqual(fleet_sensors.classify_terminal(tail, True), "unknown")



def _empty_product_hands() -> dict:
    return {
        "hand-1": {
            "actionable": 0,
            "tasks_open": 0,
            "runtime": {"state": "waiting_for_input", "process_state": "running"},
        },
        "hand-2": {
            "actionable": 0,
            "tasks_open": 0,
            "runtime": {"state": "unknown", "process_state": "running"},
        },
        "auditor-1": {
            "actionable": 0,
            "tasks_open": 0,
            "runtime": {"state": "waiting_for_input", "process_state": "running"},
        },
    }


class RefillAndCadenceHintTests(unittest.TestCase):
    def test_refill_hint_growth_empty_product_bags(self) -> None:
        out = {
            "fleet_posture": {"mode": "growth"},
            "hands": _empty_product_hands(),
            "operator": {"open_count": 0},
        }
        rh = fleet_sensors.refill_hint_from(out, [], False)
        self.assertIsNotNone(rh)
        assert rh is not None
        self.assertEqual(rh["disposition"], "file_head_lower")
        self.assertEqual(rh["signal"], "growth_refill_required")
        self.assertIn("invent_implement", rh["forbidden"])
        self.assertIn("quiet_as_ok", rh["forbidden"])

    def test_refill_hint_suppressed_when_product_bag_open(self) -> None:
        hands = _empty_product_hands()
        hands["hand-1"]["actionable"] = 1
        hands["hand-1"]["tasks_open"] = 1
        out = {"fleet_posture": {"mode": "growth"}, "hands": hands}
        self.assertIsNone(fleet_sensors.refill_hint_from(out, [], False))

    def test_refill_hint_suppressed_in_standby(self) -> None:
        out = {
            "fleet_posture": {"mode": "standby"},
            "hands": _empty_product_hands(),
        }
        self.assertIsNone(fleet_sensors.refill_hint_from(out, [], False))

    def test_cadence_does_not_shorten_on_empty_growth_starvation(self) -> None:
        out = {
            "fleet_posture": {"mode": "growth", "mind_loop_interval_sec": 900},
            "hands": _empty_product_hands(),
            "operator": {"open_count": 0},
            "refill_hint": {
                "disposition": "file_head_lower",
                "signal": "growth_refill_required",
            },
        }
        signals = [
            "growth_refill_required",
            "starvation_candidate_hand-5",
            "mail_wake_candidate_hand-1",
            "mail_wake_candidate_hand-2",
            "board_event",
            "operator_to_mind",
        ]
        ch = fleet_sensors.cadence_hint_from(out, {"quiet_streak": 0}, False, signals)
        self.assertIn("growth_empty→file_lower_not_speed", ch["reasons"])
        # Must not recommend faster than configured 15m solely for empty bags / wake noise.
        self.assertGreaterEqual(ch["recommended_interval_sec"], 900)
        self.assertNotEqual(ch["action"], "shorten")

    def test_cadence_shortens_for_idle_open_bag(self) -> None:
        hands = _empty_product_hands()
        hands["hand-1"]["actionable"] = 1
        hands["hand-1"]["tasks_open"] = 1
        hands["hand-1"]["runtime"] = {
            "state": "waiting_for_input",
            "process_state": "running",
        }
        out = {
            "fleet_posture": {"mode": "growth", "mind_loop_interval_sec": 900},
            "hands": hands,
            "operator": {"open_count": 0},
        }
        ch = fleet_sensors.cadence_hint_from(
            out, {"quiet_streak": 0}, False, ["wake_candidate_hand-1"]
        )
        self.assertEqual(ch["action"], "shorten")
        self.assertLessEqual(ch["recommended_interval_sec"], 300)
        self.assertIn("idle_open_bag→≤5m", ch["reasons"])


if __name__ == "__main__":
    unittest.main()
