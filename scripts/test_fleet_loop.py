#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def load_loop_module():
    spec = importlib.util.spec_from_file_location("fleet_loop", SCRIPTS / "fleet-loop.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FleetLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = load_loop_module()

    def test_parse_duration_accepts_common_units(self) -> None:
        self.assertEqual(self.mod.parse_duration("5m"), 300)
        self.assertEqual(self.mod.parse_duration("10min"), 600)
        self.assertEqual(self.mod.parse_duration("1h"), 3600)
        self.assertEqual(self.mod.parse_duration("90s"), 90)
        self.assertEqual(self.mod.parse_duration("300"), 300)

    def test_generated_payload_uses_fleet_cycle_and_roots_body(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = argparse.Namespace(payload=None, fleets=None)
            payload = self.mod.build_payload(root, {"fleet_id": "example"}, args)
            self.assertTrue(payload.startswith("FLEET_CYCLE fleets=example\n"))
            self.assertIn("Roots:\n  example: %s" % root, payload)

    def test_custom_payload_must_start_with_fleet_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = argparse.Namespace(payload="hello", fleets=None)
            with self.assertRaises(RuntimeError):
                self.mod.build_payload(root, {"fleet_id": "example"}, args)

    def test_custom_payload_expands_project_and_fleet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = argparse.Namespace(
                payload="FLEET_CYCLE project={project}\nFleet: {fleet}",
                fleets=None,
            )
            payload = self.mod.build_payload(root, {"fleet_id": "example"}, args)
            self.assertIn(str(root), payload)
            self.assertIn("Fleet: example", payload)


if __name__ == "__main__":
    unittest.main()
