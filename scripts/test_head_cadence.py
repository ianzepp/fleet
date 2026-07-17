#!/usr/bin/env python3
"""Unit tests for Head every_n_loops schedule resolution."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "fleet_sensors_mod",
    SCRIPTS / "fleet-sensors.py",
)
# Load module without running main: set argv and prevent SystemExit from argparse
import sys

_mod = None


def load_sensors():
    global _mod
    if _mod is not None:
        return _mod
    # fleet-sensors only runs main under __name__ == "__main__"
    _mod = importlib.util.module_from_spec(SPEC)
    assert SPEC.loader is not None
    SPEC.loader.exec_module(_mod)
    return _mod


class HeadCadenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.m = load_sensors()

    def test_explicit_zero_on_call(self) -> None:
        self.assertEqual(
            self.m.resolve_head_every_n_loops("growth", "head-cto", {"every_n_loops": 0}),
            0,
        )

    def test_explicit_n_scheduled(self) -> None:
        self.assertEqual(
            self.m.resolve_head_every_n_loops("growth", "head-cto", {"every_n_loops": 6}),
            6,
        )

    def test_legacy_enabled_false(self) -> None:
        self.assertEqual(
            self.m.resolve_head_every_n_loops("growth", "head-cto", {"enabled": False}),
            0,
        )

    def test_legacy_enabled_true_uses_posture_default(self) -> None:
        self.assertEqual(
            self.m.resolve_head_every_n_loops("growth", "head-cto", {"enabled": True}),
            6,
        )
        self.assertEqual(
            self.m.resolve_head_every_n_loops("growth", "head-ceo", {"enabled": True}),
            36,
        )

    def test_legacy_enabled_true_unknown_head_on_call(self) -> None:
        self.assertEqual(
            self.m.resolve_head_every_n_loops("growth", "head-cso", {"enabled": True}),
            0,
        )

    def test_missing_cadence_on_call(self) -> None:
        self.assertEqual(self.m.resolve_head_every_n_loops("growth", "head-cto", None), 0)
        self.assertEqual(self.m.resolve_head_every_n_loops("growth", "head-cto", {}), 0)

    def test_explicit_wins_over_enabled(self) -> None:
        self.assertEqual(
            self.m.resolve_head_every_n_loops(
                "growth", "head-cto", {"every_n_loops": 0, "enabled": True}
            ),
            0,
        )

    def test_sweep_interval_uses_n(self) -> None:
        fleet = {"mind_loop": {"interval_sec": 300}}
        self.assertEqual(
            self.m.head_sweep_interval_sec(fleet, "growth", "head-cto", 6),
            1800,
        )


if __name__ == "__main__":
    unittest.main()
