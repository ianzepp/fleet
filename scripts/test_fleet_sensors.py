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


if __name__ == "__main__":
    unittest.main()
