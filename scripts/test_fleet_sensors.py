#!/usr/bin/env python3
"""Focused tests for terminal runtime classification."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
import copy


SCRIPT = Path(__file__).with_name("fleet-sensors.py")
SPEC = importlib.util.spec_from_file_location("fleet_sensors", SCRIPT)
assert SPEC and SPEC.loader
fleet_sensors = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fleet_sensors)

BASELINE_SCRIPT = Path(__file__).with_name("fleet-baseline.py")
BASELINE_SPEC = importlib.util.spec_from_file_location("fleet_baseline", BASELINE_SCRIPT)
assert BASELINE_SPEC and BASELINE_SPEC.loader
fleet_baseline = importlib.util.module_from_spec(BASELINE_SPEC)
BASELINE_SPEC.loader.exec_module(fleet_baseline)


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

    def test_pi_hand_idle_with_update_banner(self) -> None:
        tail = """
 pi v0.80.7
 escape interrupt · ctrl+c/ctrl+d clear/exit · / commands · ! bash · ctrl+o
 more
────────────────────────────────────────────────────────────────────────────────
 Update Available
 New version 0.80.10 is available. Run pi update
────────────────────────────────────────────────────────────────────────────────
~/work/mintedgeek/swarm (main) • mgs-hand-1
0.0%/1.0M (auto)                                             (zai) glm-5.2 • low
"""
        self.assertEqual(fleet_sensors.classify_terminal(tail, True), "waiting_for_input")



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


class MemoPressureTests(unittest.TestCase):
    def test_uses_total_mailspace_count_not_display_limit(self) -> None:
        count, over = fleet_sensors.memo_pressure(
            {"memos_open": 337}, [{"handle": "one"}] * 20, 20
        )
        self.assertEqual(count, 337)
        self.assertTrue(over)

    def test_small_durable_set_is_below_budget(self) -> None:
        count, over = fleet_sensors.memo_pressure(
            {"memos_open": 9}, [{"handle": "one"}] * 9, 20
        )
        self.assertEqual(count, 9)
        self.assertFalse(over)

    def test_fingerprint_accepts_overlay_priority_goal_focus(self) -> None:
        fingerprint = fleet_sensors.build_fingerprint(
            {"hands": {}, "git": {}, "operator": {}, "steward": {}},
            {"focus": {"priority_goal": "factory/goals/railway.md"}},
        )
        self.assertEqual(fingerprint["map_focus"], "factory/goals/railway.md")


def _auditor_hand(state="waiting_for_input", actionable=0, tasks_open=0,
                  needs_open=0, paused=False, process_state="running"):
    return {
        "runtime": {"state": state, "process_state": process_state},
        "actionable": actionable,
        "tasks_open": tasks_open,
        "needs_open": needs_open,
        "operational_pause": paused,
    }


def _hands_out(*pairs):
    return {"hands": {name: row for name, row in pairs}}


def _idle_entry(idle_run, last_hint=None):
    return {"idle_run": idle_run, "last_hint_idle_run": last_hint}


class AuditorLaneClassificationTests(unittest.TestCase):
    def test_completed_and_waiting_are_healthy_idle(self) -> None:
        self.assertTrue(fleet_sensors.auditor_lane_healthy_idle(_auditor_hand("waiting_for_input")))
        self.assertTrue(fleet_sensors.auditor_lane_healthy_idle(_auditor_hand("completed")))

    def test_unhealthy_runtime_states_suppressed(self) -> None:
        for bad in ("running", "unknown", "failed", "stopped",
                    "approval_required", "starting", "submitting"):
            self.assertFalse(
                fleet_sensors.auditor_lane_healthy_idle(_auditor_hand(bad)), msg=bad)

    def test_paused_packet_or_hand_suppressed(self) -> None:
        self.assertFalse(fleet_sensors.auditor_lane_healthy_idle(_auditor_hand(paused=True)))

    def test_open_task_suppressed(self) -> None:
        self.assertFalse(fleet_sensors.auditor_lane_healthy_idle(
            _auditor_hand(actionable=1, tasks_open=1)))

    def test_open_need_suppressed(self) -> None:
        self.assertFalse(fleet_sensors.auditor_lane_healthy_idle(_auditor_hand(needs_open=1)))


class AuditorRefillHintTests(unittest.TestCase):
    def test_below_threshold_no_hint(self) -> None:
        out = _hands_out(("auditor-1", _auditor_hand()))
        baseline = {"auditor_idle": {"auditor-1": _idle_entry(3)}}
        self.assertEqual(fleet_sensors.auditor_refill_hints(out, baseline), [])

    def test_at_threshold_emits(self) -> None:
        out = _hands_out(("auditor-1", _auditor_hand()))
        baseline = {"auditor_idle": {"auditor-1": _idle_entry(4)}}
        self.assertEqual(fleet_sensors.auditor_refill_hints(out, baseline),
                         ["auditor_refill_candidate_auditor-1"])

    def test_anti_spam_requires_threshold_gap_after_hint(self) -> None:
        out = _hands_out(("auditor-1", _auditor_hand()))
        for run, emits in [(6, False), (7, False), (8, True)]:
            baseline = {"auditor_idle": {"auditor-1": _idle_entry(run, last_hint=4)}}
            sigs = fleet_sensors.auditor_refill_hints(out, baseline)
            self.assertEqual(bool(sigs), emits, msg="run=%s" % run)

    def test_high_run_but_currently_unhealthy_suppressed(self) -> None:
        out = _hands_out(("auditor-1", _auditor_hand("running")))
        baseline = {"auditor_idle": {"auditor-1": _idle_entry(20)}}
        self.assertEqual(fleet_sensors.auditor_refill_hints(out, baseline), [])

    def test_high_run_but_currently_busy_suppressed(self) -> None:
        out = _hands_out(("auditor-1", _auditor_hand(actionable=2, tasks_open=2)))
        baseline = {"auditor_idle": {"auditor-1": _idle_entry(20)}}
        self.assertEqual(fleet_sensors.auditor_refill_hints(out, baseline), [])

    def test_independent_lanes(self) -> None:
        out = _hands_out(("auditor-1", _auditor_hand()), ("auditor-2", _auditor_hand()))
        baseline = {"auditor_idle": {
            "auditor-1": _idle_entry(4),   # hints
            "auditor-2": _idle_entry(2),   # below threshold
        }}
        self.assertEqual(fleet_sensors.auditor_refill_hints(out, baseline),
                         ["auditor_refill_candidate_auditor-1"])

    def test_non_auditor_hands_excluded(self) -> None:
        out = _hands_out(
            ("hand-1", _auditor_hand()),
            ("hand-2", _auditor_hand()),
            ("auditor-1", _auditor_hand()),
        )
        baseline = {"auditor_idle": {"hand-1": _idle_entry(4), "auditor-1": _idle_entry(4)}}
        sigs = fleet_sensors.auditor_refill_hints(out, baseline)
        self.assertEqual(sigs, ["auditor_refill_candidate_auditor-1"])
        # idle map only covers auditor-* lanes
        self.assertEqual(set(out["auditor_idle"]), {"auditor-1"})

    def test_idle_map_records_unhealthy_as_false(self) -> None:
        out = _hands_out(
            ("auditor-1", _auditor_hand()),
            ("auditor-2", _auditor_hand("running")),
        )
        fleet_sensors.auditor_refill_hints(out, {"auditor_idle": {
            "auditor-1": _idle_entry(0), "auditor-2": _idle_entry(0)}})
        self.assertEqual(out["auditor_idle"], {"auditor-1": True, "auditor-2": False})

    def test_no_persisted_entry_treated_as_zero(self) -> None:
        out = _hands_out(("auditor-1", _auditor_hand()))
        # fresh auditor, no baseline bookkeeping -> idle_run 0 -> no hint
        self.assertEqual(fleet_sensors.auditor_refill_hints(out, {}), [])
        self.assertEqual(out["auditor_idle"], {"auditor-1": True})

    def test_poll_stability_idempotent_and_non_mutating(self) -> None:
        baseline = {"auditor_idle": {"auditor-1": _idle_entry(4)}}
        snapshot = copy.deepcopy(baseline)
        first = fleet_sensors.auditor_refill_hints(
            _hands_out(("auditor-1", _auditor_hand())), baseline)
        second = fleet_sensors.auditor_refill_hints(
            _hands_out(("auditor-1", _auditor_hand())), baseline)
        self.assertEqual(first, second)
        # sensors must not mutate baseline bookkeeping (counting is bump-only)
        self.assertEqual(baseline, snapshot)


class AuditorIdlePersistenceTests(unittest.TestCase):
    def test_advances_on_healthy_idle(self) -> None:
        b = {"auditor_idle": {"auditor-1": _idle_entry(2)}}
        fleet_baseline.apply_auditor_idle_state(
            b, {"auditor_idle": {"auditor-1": True}, "signals": []})
        self.assertEqual(b["auditor_idle"]["auditor-1"]["idle_run"], 3)
        self.assertIsNone(b["auditor_idle"]["auditor-1"]["last_hint_idle_run"])

    def test_resets_on_work_or_unhealthy(self) -> None:
        b = {"auditor_idle": {"auditor-1": _idle_entry(9, last_hint=8)}}
        fleet_baseline.apply_auditor_idle_state(
            b, {"auditor_idle": {"auditor-1": False}, "signals": []})
        self.assertEqual(b["auditor_idle"]["auditor-1"]["idle_run"], 0)
        self.assertIsNone(b["auditor_idle"]["auditor-1"]["last_hint_idle_run"])

    def test_stamps_last_hint_when_signal_present(self) -> None:
        # sensors emitted this cycle using prev_run=3; baseline stamps last_hint=3
        b = {"auditor_idle": {"auditor-1": _idle_entry(3)}}
        fleet_baseline.apply_auditor_idle_state(
            b, {"auditor_idle": {"auditor-1": True},
                "signals": ["auditor_refill_candidate_auditor-1"]})
        self.assertEqual(b["auditor_idle"]["auditor-1"]["idle_run"], 4)
        self.assertEqual(b["auditor_idle"]["auditor-1"]["last_hint_idle_run"], 3)

    def test_keeps_last_hint_when_healthy_no_signal(self) -> None:
        b = {"auditor_idle": {"auditor-1": _idle_entry(6, last_hint=4)}}
        fleet_baseline.apply_auditor_idle_state(
            b, {"auditor_idle": {"auditor-1": True}, "signals": []})
        self.assertEqual(b["auditor_idle"]["auditor-1"]["idle_run"], 7)
        self.assertEqual(b["auditor_idle"]["auditor-1"]["last_hint_idle_run"], 4)

    def test_independent_lanes(self) -> None:
        b = {"auditor_idle": {
            "auditor-1": _idle_entry(3),
            "auditor-2": _idle_entry(5, last_hint=4),
        }}
        fleet_baseline.apply_auditor_idle_state(b, {
            "auditor_idle": {"auditor-1": True, "auditor-2": False},
            "signals": ["auditor_refill_candidate_auditor-1"],
        })
        self.assertEqual(b["auditor_idle"]["auditor-1"],
                         {"idle_run": 4, "last_hint_idle_run": 3})
        self.assertEqual(b["auditor_idle"]["auditor-2"],
                         {"idle_run": 0, "last_hint_idle_run": None})

    def test_non_auditor_keys_ignored(self) -> None:
        b = {"auditor_idle": {"auditor-1": _idle_entry(3)}}
        fleet_baseline.apply_auditor_idle_state(
            b, {"auditor_idle": {"hand-1": True, "auditor-1": True}, "signals": []})
        self.assertNotIn("hand-1", b["auditor_idle"])
        self.assertEqual(b["auditor_idle"]["auditor-1"]["idle_run"], 4)

    def test_noop_without_auditor_idle_map(self) -> None:
        b = {"auditor_idle": {"auditor-1": _idle_entry(3)}}
        snapshot = copy.deepcopy(b)
        fleet_baseline.apply_auditor_idle_state(
            b, {"signals": ["auditor_refill_candidate_auditor-1"]})
        self.assertEqual(b, snapshot)


class AuditorRefillCycleContractTests(unittest.TestCase):
    """End-to-end sensor+bump contract: 4 completed idle cycles -> hint, then
    4 more -> next hint. Counting uses baseline advancement, not poll/wall time."""

    def _run_cycle(self, baseline, hand, name="auditor-1"):
        out = _hands_out((name, hand))
        sigs = fleet_sensors.auditor_refill_hints(out, baseline)
        nb = copy.deepcopy(baseline)
        fleet_baseline.apply_auditor_idle_state(
            nb, {"auditor_idle": out["auditor_idle"], "signals": list(sigs)})
        return nb, sigs

    def test_threshold_then_antispam(self) -> None:
        healthy = _auditor_hand("waiting_for_input")
        baseline: dict = {}

        # 4 completed idle cycles accrue idle_run 1..4; no hint yet
        for _ in range(4):
            baseline, sigs = self._run_cycle(baseline, healthy)
            self.assertEqual(sigs, [])
        self.assertEqual(baseline["auditor_idle"]["auditor-1"]["idle_run"], 4)

        # 5th cycle: sensors reads idle_run=4 -> first hint; bump stamps last_hint=4
        baseline, sigs = self._run_cycle(baseline, healthy)
        self.assertEqual(sigs, ["auditor_refill_candidate_auditor-1"])
        self.assertEqual(baseline["auditor_idle"]["auditor-1"]["idle_run"], 5)
        self.assertEqual(baseline["auditor_idle"]["auditor-1"]["last_hint_idle_run"], 4)

        # 3 more completed idle cycles: anti-spam suppresses (gaps 1, 2, 3)
        for _ in range(3):
            baseline, sigs = self._run_cycle(baseline, healthy)
            self.assertEqual(sigs, [])
        self.assertEqual(baseline["auditor_idle"]["auditor-1"]["idle_run"], 8)

        # gap reaches 4 -> second hint
        baseline, sigs = self._run_cycle(baseline, healthy)
        self.assertEqual(sigs, ["auditor_refill_candidate_auditor-1"])

    def test_work_resets_streak_and_re_accrues(self) -> None:
        healthy = _auditor_hand("waiting_for_input")
        busy = _auditor_hand(actionable=1, tasks_open=1)
        baseline: dict = {}

        for _ in range(4):
            baseline, _ = self._run_cycle(baseline, healthy)
        self.assertEqual(baseline["auditor_idle"]["auditor-1"]["idle_run"], 4)

        # one busy cycle resets the streak to zero
        baseline, sigs = self._run_cycle(baseline, busy)
        self.assertEqual(baseline["auditor_idle"]["auditor-1"]["idle_run"], 0)
        self.assertEqual(sigs, [])

        # needs a fresh 4 completed idle cycles before the next hint
        for _ in range(4):
            baseline, sigs = self._run_cycle(baseline, healthy)
            self.assertEqual(sigs, [])
        baseline, sigs = self._run_cycle(baseline, healthy)
        self.assertEqual(sigs, ["auditor_refill_candidate_auditor-1"])


if __name__ == "__main__":
    unittest.main()
