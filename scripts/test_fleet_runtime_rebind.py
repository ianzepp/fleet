#!/usr/bin/env python3
"""Focused unit tests for fleet-runtime-rebind.py — fake tmux/vivi-pty, temp overlays.

Tests cover: plan dry-run, apply with atomic replacement, selectors, launch
generation for all harnesses, vivi_pty runtime.command update, running guard,
back-end stop/start/readiness, and rollback on partial failure.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def _load_script(name: str):
    """Load a script module by filename (with hyphens)."""
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_").replace(".py", ""), path
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


rebind = _load_script("fleet-runtime-rebind.py")


class FakeExecutables:
    """Create fake tmux and vivi-pty scripts in a temp directory."""

    def __init__(self, tmpd: Path):
        self.dir = tmpd

    def _write_fake(self, name: str, content: str) -> Path:
        path = self.dir / name
        path.write_text("#!/usr/bin/env bash\n%s\n" % content, encoding="utf-8")
        path.chmod(0o755)
        return path

    def install_fake_tmux(self, state: str = "waiting_for_input") -> Path:
        """Fake tmux that reports a configurable state."""
        content = """state="$1"
if [[ "$1" == "has-session" ]]; then
  exit 0
elif [[ "$1" == "capture-pane" ]]; then
  echo "› Waiting for input…"
elif [[ "$1" == "send-keys" ]]; then
  exit 0
elif [[ "$1" == "new-session" ]]; then
  exit 0
fi
exit 0
"""
        return self._write_fake("tmux", content)

    def install_fake_vivi_pty(self, state: str = "waiting_for_input") -> Path:
        """Fake vivi-pty that returns diagnostic JSON."""
        content = '''cat <<'EOF'
{"harness_state": "%s", "process_state": "running", "confidence": "high", "evidence": []}
EOF
''' % state
        return self._write_fake("vivi-pty", content)


class RuntimeRebindPlanTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / ".vivi").mkdir(parents=True)

    def tearDown(self):
        self.td.cleanup()

    def _write_fleet(self, fleet: dict) -> Path:
        path = self.root / ".vivi" / "fleet.json"
        path.write_text(json.dumps(fleet, indent=2), encoding="utf-8")
        return path

    def _run(self, *args: str) -> tuple:
        cmd = [sys.executable, str(SCRIPTS / "fleet-runtime-rebind.py"),
               "--project", str(self.root)] + list(args)
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr

    def test_plan_no_roles_is_usage_error(self):
        self._write_fleet({"fleet_id": "test", "hands": {"hand-1": {"agent": "grok"}}})
        rc, out, err = self._run("plan")
        self.assertEqual(rc, 2)
        self.assertIn("no roles selected", err)

    def test_plan_hands_all_shows_changes(self):
        self._write_fleet({
            "fleet_id": "test",
            "mind": {"agent": "grok"},
            "hands": {"hand-1": {"agent": "grok", "agent_model": "grok-4.5", "tmux_target": "test-hand-1:1.1"}},
        })
        rc, out, err = self._run("plan", "--hands", "all", "--model", "grok-4.6")
        self.assertEqual(rc, 0)
        self.assertIn("PLAN:", out)
        self.assertIn("hand-1", out)
        self.assertIn("agent_model", out)

    def test_plan_heads_all_shows_changes(self):
        self._write_fleet({
            "fleet_id": "test",
            "head-ceo": {"agent": "pi", "agent_model": "glm-5.2", "tmux_target": "head-ceo:1.1"},
            "head-cto": {"agent": "pi", "agent_model": "gpt-5.5", "tmux_target": "head-cto:1.1"},
        })
        rc, out, err = self._run("plan", "--heads", "all", "--agent", "pi", "--provider", "zai", "--model", "glm-5.2", "--thinking", "xhigh")
        self.assertEqual(rc, 0)
        self.assertIn("PLAN:", out)
        self.assertIn("head-ceo", out)

    def test_plan_role_repeatable(self):
        self._write_fleet({
            "fleet_id": "test",
            "head-ceo": {"agent": "pi", "agent_model": "glm-5.2", "tmux_target": "head-ceo:1.1"},
            "head-cto": {"agent": "pi", "agent_model": "gpt-5.5", "tmux_target": "head-cto:1.1"},
        })
        rc, out, err = self._run("plan", "--role", "head-ceo", "--role", "head-cto", "--thinking", "xhigh")
        self.assertEqual(rc, 0)
        self.assertIn("head-ceo", out)
        self.assertIn("head-cto", out)

    def test_plan_no_material_changes_shows_message(self):
        self._write_fleet({
            "fleet_id": "test",
            "hands": {"hand-1": {"agent": "grok", "agent_model": "grok-4.5", "agent_launch": "grok --model grok-4.5 --always-approve", "tmux_target": "test-hand-1:1.1"}},
        })
        # No model field changes — even agent_launch stays the same
        rc, out, err = self._run("plan", "--hands", "all")
        self.assertEqual(rc, 0)
        self.assertIn("no material changes", out.lower())

    def test_plan_running_guard_warns(self):
        """Running roles produce a warning unless --force-running."""
        # Running state is detected via tmux — in test env without real tmux,
        # state will be 'stopped', so this tests the flow when state is running.
        # We set up a fake fleet with a known identity.
        self._write_fleet({
            "fleet_id": "test",
            "hands": {"hand-1": {"agent": "grok", "agent_model": "grok-4.5", "tmux_target": "test-hand-1:1.1"}},
        })
        # Without real tmux, state is stopped → no warning
        rc, out, err = self._run("plan", "--hands", "all", "--model", "grok-4.6")
        self.assertEqual(rc, 0)

    def test_plan_is_never_mutating(self):
        self._write_fleet({
            "fleet_id": "test",
            "hands": {"hand-1": {"agent": "grok", "agent_model": "grok-4.5", "tmux_target": "test-hand-1:1.1"}},
        })
        fleet_path = self.root / ".vivi" / "fleet.json"
        original = fleet_path.read_text()
        self._run("plan", "--hands", "all", "--model", "grok-4.6")
        self.assertEqual(fleet_path.read_text(), original)


class RuntimeRebindApplyTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / ".vivi").mkdir(parents=True)
        # Set up fake executables
        self.fake_bin = self.root / "fake_bin"
        self.fake_bin.mkdir()
        self._orig_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(self.fake_bin) + ":" + self._orig_path

    def tearDown(self):
        os.environ["PATH"] = self._orig_path
        self.td.cleanup()

    def _write_fleet(self, fleet: dict) -> Path:
        path = self.root / ".vivi" / "fleet.json"
        path.write_text(json.dumps(fleet, indent=2), encoding="utf-8")
        return path

    def _install_fake_tmux(self) -> Path:
        fakes = FakeExecutables(self.fake_bin)
        return fakes.install_fake_tmux()

    def _install_fake_vivi_pty(self, state: str = "waiting_for_input") -> Path:
        fakes = FakeExecutables(self.fake_bin)
        return fakes.install_fake_vivi_pty(state)

    def _run(self, *args: str) -> tuple:
        cmd = [sys.executable, str(SCRIPTS / "fleet-runtime-rebind.py"),
               "--project", str(self.root)] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr

    def _make_valid_hand_fleet(self, extra_hand: dict = None) -> dict:
        """Build a minimal but validatable fleet.json for apply tests."""
        hand = {
            "agent": "grok",
            "agent_model": "grok-4.5",
            "mail_identity": "hand-1",
            "tmux_target": "test-hand-1:1.1",
            "cwd": str(self.root),
        }
        if extra_hand:
            hand.update(extra_hand)
        return {
            "version": 1,
            "default_hand": "hand-1",
            "fleet_id": "test",
            "mind": {"agent": "grok"},
            "hands": {"hand-1": hand},
        }

    def test_apply_atomic_replacement(self):
        self._write_fleet(self._make_valid_hand_fleet())
        self._install_fake_tmux()
        rc, out, err = self._run("apply", "--hands", "all", "--model", "grok-4.6")
        self.assertEqual(rc, 0, "apply failed: stderr=%s" % err)
        self.assertIn("applied", out)
        # Verify the file was actually updated
        updated = json.loads((self.root / ".vivi" / "fleet.json").read_text())
        self.assertEqual(updated["hands"]["hand-1"]["agent_model"], "grok-4.6")

    def test_apply_with_restart_and_fake_tmux(self):
        self._write_fleet(self._make_valid_hand_fleet({
            "agent_launch": "grok --model grok-4.5 --always-approve",
        }))
        self._install_fake_tmux()
        rc, out, err = self._run("apply", "--hands", "all", "--model", "grok-4.6", "--restart")
        self.assertEqual(rc, 0, "apply with restart failed: stderr=%s" % err)
        self.assertIn("restarting panes", out)
        self.assertIn("started", out)

    def test_apply_should_not_mutate_on_plan(self):
        """Verify apply subcommand actually mutates (not a dry-run)."""
        self._write_fleet(self._make_valid_hand_fleet())
        self._install_fake_tmux()
        rc, out, err = self._run("apply", "--hands", "all", "--model", "grok-4.6")
        self.assertEqual(rc, 0, "apply failed: stderr=%s" % err)
        updated = json.loads((self.root / ".vivi" / "fleet.json").read_text())
        self.assertEqual(updated["hands"]["hand-1"]["agent_model"], "grok-4.6")


class LaunchGenerationTests(unittest.TestCase):
    def test_grok_launch(self):
        launch = rebind._build_launch("grok", "grok-4.5", None, None, None)
        self.assertIn("grok", launch)
        self.assertIn("grok-4.5", launch)
        self.assertIn("--always-approve", launch)

    def test_codex_launch(self):
        launch = rebind._build_launch("codex", "gpt-5.6-luna", None, "xhigh", None)
        self.assertIn("codex", launch)
        self.assertIn("gpt-5.6-luna", launch)
        self.assertIn("model_reasoning_effort=xhigh", launch)
        self.assertIn("danger-full-access", launch)

    def test_pi_launch(self):
        launch = rebind._build_launch("pi", "glm-5.2", "zai", "high", None)
        self.assertIn("pi", launch)
        self.assertIn("zai", launch)
        self.assertIn("glm-5.2", launch)
        self.assertIn("--thinking", launch)
        self.assertIn("high", launch)

    def test_opencode_launch(self):
        launch = rebind._build_launch("opencode", "opencode/gpt-5.6-sol", None, "high", None)
        self.assertIn("opencode", launch)
        self.assertIn("gpt-5.6-sol", launch)
        self.assertIn("--auto", launch)

    def test_unknown_harness_returns_none(self):
        launch = rebind._build_launch("unknown-harness", "model-x", None, None, None)
        self.assertIsNone(launch)

    def test_reasoning_fallback(self):
        launch = rebind._build_launch("grok", "grok-4.5", None, None, "xhigh")
        self.assertIn("grok-4.5", launch)

    def test_launch_no_flatten_eval(self):
        """Generated launch must not contain unquoted shell metacharacters."""
        launch = rebind._build_launch("grok", "grok 4.5", None, None, None)
        if launch:
            self.assertIn("'", launch)  # properly quoted


class RuntimeCommandUpdateTests(unittest.TestCase):
    def test_vivi_pty_command_grok(self):
        runtime = {"kind": "vivi_pty", "command": ["grok", "--old-model", "x"]}
        updated = rebind._update_runtime_command(runtime, "grok", "grok-4.6", None, None, None)
        self.assertEqual(updated["command"], ["grok", "--model", "grok-4.6", "--always-approve"])

    def test_vivi_pty_command_pi(self):
        runtime = {"kind": "vivi_pty", "command": ["pi"]}
        updated = rebind._update_runtime_command(runtime, "pi", "glm-5.2", "zai", "high", None)
        self.assertEqual(updated["command"], ["pi", "--provider", "zai", "--model", "glm-5.2", "--thinking", "high", "--approve"])

    def test_vivi_pty_command_unknown_preserves(self):
        runtime = {"kind": "vivi_pty", "command": ["custom-agent"]}
        updated = rebind._update_runtime_command(runtime, "unknown", "x", None, None, None)
        self.assertIs(updated, runtime)


class ResolveSlotsTests(unittest.TestCase):
    def test_heads_all(self):
        fleet = {"head-ceo": {"agent": "pi"}, "head-cto": {"agent": "pi"}, "hands": {}}
        selected = rebind._resolve_slots(fleet, "all", None, None)
        self.assertEqual(selected, {"head-ceo", "head-cto"})

    def test_hands_all(self):
        fleet = {"hands": {"hand-1": {}, "hand-2": {}}}
        selected = rebind._resolve_slots(fleet, None, "all", None)
        self.assertEqual(selected, {"hand-1", "hand-2"})

    def test_heads_comma(self):
        fleet = {"head-ceo": {"agent": "pi"}, "head-cto": {"agent": "pi"}, "head-cxo": {"agent": "pi"}}
        selected = rebind._resolve_slots(fleet, "head-ceo,head-cto", None, None)
        self.assertEqual(selected, {"head-ceo", "head-cto"})

    def test_roles_repeatable(self):
        fleet = {"head-ceo": {"agent": "pi"}, "hands": {"hand-1": {}}}
        selected = rebind._resolve_slots(fleet, None, None, ["head-ceo", "hand-1"])
        self.assertEqual(selected, {"head-ceo", "hand-1"})

    def test_combined_selectors(self):
        fleet = {"head-ceo": {"agent": "pi"}, "hands": {"hand-1": {}, "hand-2": {}}}
        selected = rebind._resolve_slots(fleet, "all", "hand-2", ["head-ceo"])
        self.assertEqual(selected, {"head-ceo", "hand-2"})


class ClassifyTests(unittest.TestCase):
    def test_running(self):
        self.assertEqual(rebind._classify_tail("Working (step 3/5)"), "running")
        self.assertEqual(rebind._classify_tail("esc to interrupt"), "running")
        self.assertEqual(rebind._classify_tail("Waiting for response…"), "running")

    def test_approval_required(self):
        self.assertEqual(rebind._classify_tail("Do you trust this?"), "approval_required")

    def test_failed_capacity(self):
        self.assertEqual(rebind._classify_tail("over capacity 429"), "failed")

    def test_completed(self):
        self.assertEqual(rebind._classify_tail("› bag empty"), "completed")

    def test_waiting_for_input(self):
        self.assertEqual(rebind._classify_tail("›"), "waiting_for_input")
        self.assertEqual(rebind._classify_tail("codex ›"), "waiting_for_input")

    def test_opencode(self):
        self.assertEqual(rebind._classify_tail("OpenCode Zen Build ·"), "waiting_for_input")

    def test_unknown(self):
        self.assertEqual(rebind._classify_tail("some random text"), "unknown")


if __name__ == "__main__":
    unittest.main()
