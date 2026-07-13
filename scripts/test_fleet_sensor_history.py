#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


sensors = load_script("fleet-sensors.py")
validator = load_script("verify-fleet-json.py")


class SensorHistoryTest(unittest.TestCase):
    def project(self, sensor_log=None):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / ".vivi").mkdir()
        fleet = {"fleet_id": "test", "hands": {}}
        if sensor_log is not None:
            fleet["sensor_log"] = sensor_log
        (root / ".vivi" / "fleet.json").write_text(json.dumps(fleet), encoding="utf-8")
        return td, root

    def invoke(self, root, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "fleet-sensors.py"), "--project", str(root), "--no-watch", *args],
            text=True, capture_output=True, check=False,
        )

    def test_disabled_default_does_not_write(self):
        td, root = self.project()
        with td:
            result = self.invoke(root, "--record-cycle")
            self.assertEqual(json.loads(result.stdout)["sensor_log"]["status"], "disabled")
            self.assertFalse((root / ".vivi" / "logs" / "sensors").exists())

    def test_summary_idempotency_retention_and_history(self):
        td, root = self.project({"enabled": True, "level": "summary", "retention_cycles": 2})
        with td:
            first = self.invoke(root, "--record-cycle", "--cycle-id", "1")
            self.assertEqual(json.loads(first.stdout)["sensor_log"]["status"], "recorded")
            retry = self.invoke(root, "--record-cycle", "--cycle-id", "1")
            self.assertEqual(json.loads(retry.stdout)["sensor_log"]["status"], "idempotent")
            self.invoke(root, "--record-cycle", "--cycle-id", "2")
            self.invoke(root, "--record-cycle", "--cycle-id", "3")
            files = sorted((root / ".vivi" / "logs" / "sensors").glob("*.json"))
            self.assertEqual([p.name for p in files], ["2.json", "3.json"])
            history = self.invoke(root, "--history", "1")
            records = json.loads(history.stdout)["history"]
            self.assertEqual([r["cycle_id"] for r in records], ["3"])
            self.assertEqual(records[0]["level"], "summary")

    def test_redaction_and_model_mismatch(self):
        redacted = sensors.redact_snapshot({
            "runtime": {"tail": "private", "tail_hash": "ok", "evidence": ["private"]},
            "mail": {"subject": "customer", "body": "secret", "handle": "abc"},
            "api_token": "secret",
        })
        self.assertNotIn("tail", redacted["runtime"])
        self.assertNotIn("evidence", redacted["runtime"])
        self.assertNotIn("subject", redacted["mail"])
        self.assertNotIn("api_token", redacted)
        provenance = sensors.model_provenance(
            {"agent": "codex", "provider": "openai", "model": "configured"},
            {"agent": "codex", "provider": "openai", "model": "observed"},
        )
        self.assertEqual(provenance["match_status"], "mismatch")

    def test_mgs_shaped_configured_provenance(self):
        fleet = {
            "preferred_models": {
                "head": {"agent": "pi", "provider": "zai", "model": "glm-default", "thinking": "xhigh"},
                "codex": {"hand": {"provider": "openai", "model": "gpt-default", "effort": "medium"}},
                "grok": {"hand": "grok-4.5"},
            }
        }
        head = sensors.model_provenance(
            {"agent": "pi", "agent_model": "glm-5.2", "thinking": "high", "agent_launch": "pi --provider false"},
            fleet=fleet,
            role="head",
        )
        self.assertEqual(head["configured"], {
            "agent": "pi", "provider": "zai", "model": "glm-5.2", "reasoning": "high",
        })
        hand = sensors.model_provenance(
            {"agent": "codex", "agent_model": "gpt-5.6-luna", "agent_reasoning_effort": "xhigh"},
            fleet=fleet,
            role="hand",
        )
        self.assertEqual(hand["configured"], {
            "agent": "codex", "provider": "openai", "model": "gpt-5.6-luna", "reasoning": "xhigh",
        })
        grok = sensors.model_provenance({"agent": "grok"}, fleet=fleet, role="hand")
        self.assertEqual(grok["configured"], {"agent": "grok", "model": "grok-4.5"})

    def test_history_role_filter_covers_event_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            record = {
                "schema_version": 1,
                "cycle_id": "1",
                "observation": {"model_provenance": {"hand-1": {"match_status": "match"}, "hand-2": {"match_status": "mismatch"}}},
            }
            (directory / "1.json").write_text(json.dumps(record), encoding="utf-8")
            filtered = sensors.read_history(directory, 1, "hand-1")
            self.assertEqual(list(filtered[0]["observation"]["model_provenance"]), ["hand-1"])

    def test_zero_history_and_cli_validation(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            (directory / "1.json").write_text(json.dumps({"cycle_id": "1"}), encoding="utf-8")
            self.assertEqual(sensors.read_history(directory, 0, None), [])
        td, root = self.project()
        with td:
            invalid = [
                ("--role", "hand-1"),
                ("--cycle-id", "1"),
                ("--history", "1", "--record-cycle"),
                ("--history", "1", "--text"),
                ("--record-cycle", "--cycle-id", "01"),
                ("--history", "1", "--role", "missing"),
            ]
            for args in invalid:
                result = self.invoke(root, *args)
                self.assertEqual(result.returncode, 2, (args, result.stderr))
                self.assertTrue(result.stderr.strip())

    def test_nested_observed_model_and_identity_match_gate(self):
        observed = sensors._observed_model({
            "agent": "pi",
            "runtime": {"model_provenance": {"provider": "zai"}},
            "session": {"model": "glm-5.2", "reasoning": "high"},
        })
        self.assertEqual(observed, {
            "agent": "pi", "provider": "zai", "model": "glm-5.2", "reasoning": "high",
        })
        partial = sensors.model_provenance(
            {"agent": "pi", "agent_model": "glm-5.2"},
            {"agent": "pi", "provider": "zai"},
        )
        self.assertEqual(partial["match_status"], "unknown")
        matched = sensors.model_provenance(
            {"agent": "pi", "agent_model": "glm-5.2"}, observed,
        )
        self.assertEqual(matched["match_status"], "match")

    def test_concurrent_first_write_wins_and_metadata_conflicts(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            barrier = threading.Barrier(2)
            outcomes = []
            lock = threading.Lock()

            def writer(level):
                barrier.wait()
                try:
                    result = sensors.record_history(
                        {"fleet_id": level, "signals": [], "fingerprint": {}},
                        {"path": directory, "level": level, "retention_cycles": 10},
                        "7", "2026-01-01T00:00:00+00:00",
                    )
                    outcome = result["status"]
                except sensors.CycleConflictError:
                    outcome = "conflict"
                with lock:
                    outcomes.append(outcome)

            threads = [threading.Thread(target=writer, args=(level,)) for level in ("summary", "events")]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertCountEqual(outcomes, ["recorded", "conflict"])
            stored = json.loads((directory / "7.json").read_text(encoding="utf-8"))
            self.assertIn(stored["level"], ("summary", "events"))
            self.assertEqual(stored["cycle_id"], "7")
            with self.assertRaises(sensors.CycleConflictError):
                sensors.record_history({}, {"path": directory, "level": "full"}, "7", "later")
            self.assertEqual(json.loads((directory / "7.json").read_text(encoding="utf-8")), stored)
            with self.assertRaises(ValueError):
                sensors.record_history({}, {"path": directory, "level": "summary"}, "alpha", "now")

    def test_full_persisted_record_excludes_realistic_content(self):
        with tempfile.TemporaryDirectory() as td:
            directory = Path(td)
            out = {
                "fleet_id": "test",
                "hands": {"hand-1": {"runtime": {"tail": "customer pane body", "tail_hash": "safehash", "evidence": ["raw"]}}},
                "heads": {"head-cto": {"runtime": {"contents": "private"}}},
                "operator": {"to_mind": [{"subject": "customer name", "body": "mail body", "handle": "abc"}]},
                "watch": {"event": "mail body"},
                "api_token": "secret",
                "fingerprint": {"map_focus": "customer project", "hand1_state": "running"},
            }
            sensors.record_history(out, {"path": directory, "level": "full"}, "1", "now")
            persisted = (directory / "1.json").read_text(encoding="utf-8")
            for secret in ("customer pane body", "private", "raw", "customer name", "mail body", "secret", "customer project"):
                self.assertNotIn(secret, persisted)
            self.assertIn("safehash", persisted)

    def test_sensor_log_validation(self):
        report = validator.validate(
            {"sensor_log": {"enabled": "yes", "level": "verbose", "retention_cycles": 0}},
            Path("fleet.json"), False,
        )
        locations = {where for where, _ in report.errors}
        self.assertIn("$.sensor_log.enabled", locations)
        self.assertIn("$.sensor_log.level", locations)
        self.assertIn("$.sensor_log.retention_cycles", locations)


if __name__ == "__main__":
    unittest.main()
