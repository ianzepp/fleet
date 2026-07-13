#!/usr/bin/env python3
"""Focused tests for the shared fleet scope and runtime resolver."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from fleet_common import (  # noqa: E402
    FleetScopeError,
    resolve_fleet_file,
    resolve_runtime_binding,
)


class FleetResolverTests(unittest.TestCase):
    def write_fleet(self, root: Path, data: dict) -> None:
        overlay = root / ".vivi"
        overlay.mkdir()
        (overlay / "fleet.json").write_text(json.dumps(data), encoding="utf-8")

    def test_session_per_fleet_derives_session_and_window_from_logical_values(self) -> None:
        fleet = {
            "fleet_id": "example",
            "tmux_layout": "session_per_fleet",
            "hands": {"hand-1": {"mail_identity": "hand-1", "cwd": "/tmp"}},
        }
        binding = resolve_runtime_binding(fleet, "hand-1", project="/tmp/example")
        self.assertEqual(binding["fleet_id"], "example")
        self.assertEqual(binding["session"], "example")
        self.assertEqual(binding["window"], "hand-1")
        self.assertEqual(binding["target"], "example:hand-1.1")

    def test_legacy_layout_does_not_assume_session_per_fleet(self) -> None:
        fleet = {
            "fleet_id": "example",
            "tmux_layout": "legacy",
            "hands": {"hand-1": {"mail_identity": "hand-1"}},
        }
        binding = resolve_runtime_binding(fleet, "hand-1", project="/tmp/example")
        self.assertEqual(binding["target"], "hand-1:1.1")

    def test_explicit_target_wins_and_is_parsed(self) -> None:
        fleet = {
            "fleet_id": "example",
            "tmux_layout": "session_per_fleet",
            "hands": {"hand-1": {"tmux_target": "custom:window.2"}},
        }
        binding = resolve_runtime_binding(fleet, "hand-1", project="/tmp/example")
        self.assertEqual(binding["session"], "custom")
        self.assertEqual(binding["window"], "window")
        self.assertEqual(binding["pane"], "2")

    def test_vivi_pty_binding_keeps_backend_specific_session(self) -> None:
        fleet = {
            "fleet_id": "example",
            "hands": {
                "hand-1": {
                    "agent": "grok",
                    "runtime": {
                        "kind": "vivi_pty",
                        "session_id": "hand-1",
                        "driver": "grok",
                        "command": ["grok", "--model", "model-x"],
                    },
                }
            },
        }
        binding = resolve_runtime_binding(fleet, "hand-1", project="/tmp/example")
        self.assertEqual(binding["kind"], "vivi_pty")
        self.assertEqual(binding["target"], "hand-1")
        self.assertEqual(binding["driver"], "grok")
        self.assertEqual(binding["runtime_command"], ["grok", "--model", "model-x"])

    def test_fleet_id_is_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fleet(root, {"fleet_id": "example", "hands": {}})
            with self.assertRaises(FleetScopeError):
                resolve_fleet_file(root, fleet_id="other")

    def test_resolver_cli_emits_shell_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fleet(
                root,
                {
                    "fleet_id": "example",
                    "tmux_layout": "session_per_fleet",
                    "hands": {"hand-1": {"agent": "grok"}},
                },
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "fleet-resolve.py"),
                    "--project",
                    str(root),
                    "--fleet",
                    "example",
                    "--role",
                    "hand-1",
                    "--shell",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("RESOLVED_TARGET=example:hand-1.1", result.stdout)

    def test_resolver_cli_lists_filtered_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fleet(
                root,
                {
                    "fleet_id": "example",
                    "hands": {
                        "hand-1": {"agent": "codex"},
                        "hand-2": {"agent": "opencode"},
                    },
                },
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "fleet-resolve.py"),
                    "--project", str(root), "--fleet", "example", "--list",
                    "--agent", "codex", "--group", "hand",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "hand-1")

    def test_baseline_cli_accepts_scope_before_and_after_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_fleet(root, {"fleet_id": "example", "hands": {}})
            for args in (
                ["--project", str(root), "get"],
                ["get", "--project", str(root)],
                ["bump", "--project", str(root), "--summary", "sleep", "--quiet"],
            ):
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS / "fleet-baseline.py"), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
