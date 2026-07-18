#!/usr/bin/env python3
"""Tests for backend-neutral fleet-runtime.py lifecycle helper."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


class RuntimeHelperTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        (self.root / ".vivi").mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.orig_path = os.environ.get("PATH", "")
        os.environ["PATH"] = str(self.bin) + os.pathsep + self.orig_path

    def tearDown(self):
        os.environ["PATH"] = self.orig_path
        self.td.cleanup()

    def write_fleet(self, fleet):
        path = self.root / ".vivi" / "fleet.json"
        path.write_text(json.dumps(fleet), encoding="utf-8")

    def write_fake(self, name: str, body: str):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
        path.chmod(0o755)
        return path

    def run_helper(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "fleet-runtime.py"), "--project", str(self.root), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def install_fake_vivi_pty(self):
        self.write_fake(
            "vivi-pty",
            r'''
state_file="$TMPDIR/fake-vivi-pty-state-${3:-default}"
if [[ "$1" == "info" ]]; then exit 0; fi
if [[ "$1" == "daemon" ]]; then sleep 60; exit 0; fi
if [[ "$1" == "session" && "$2" == "diagnostic" ]]; then
  sid="$3"; f="$TMPDIR/fake-vivi-pty-state-$sid"
  if [[ -f "$f" ]]; then st=$(cat "$f"); else st=stopped; fi
  cat <<EOF
{"process_state":"$st","harness_state":"waiting_for_input","confidence":"high","session":{"state":"$st"}}
EOF
  exit 0
fi
if [[ "$1" == "session" && "$2" == "inspect" ]]; then
  sid="$3"; f="$TMPDIR/fake-vivi-pty-state-$sid"
  [[ -f "$f" ]] || exit 1
  st=$(cat "$f")
  cmd_f="$TMPDIR/fake-vivi-pty-cmd-$sid"
  if [[ -f "$cmd_f" ]]; then cmd=$(cat "$cmd_f"); else cmd='["pi","--model","fake"]'; fi
  echo "{\"state\":\"$st\",\"command\":$cmd}"
  exit 0
fi
if [[ "$1" == "session" && "$2" == "start" ]]; then
  sid="$3"
  echo running > "$TMPDIR/fake-vivi-pty-state-$sid"
  # Capture argv after the first bare "--" separator.
  python3 - "$sid" "$@" <<'PY'
import json, sys
sid = sys.argv[1]
args = sys.argv[2:]
cmd = []
if "--" in args:
    cmd = args[args.index("--") + 1 :]
open(__import__("os").environ["TMPDIR"] + f"/fake-vivi-pty-cmd-{sid}", "w").write(json.dumps(cmd))
PY
  exit 0
fi
if [[ "$1" == "session" && "$2" == "restart" ]]; then
  echo running > "$TMPDIR/fake-vivi-pty-state-$3"
  exit 0
fi
if [[ "$1" == "session" && "$2" == "stop" ]]; then
  echo stopped > "$TMPDIR/fake-vivi-pty-state-$3"
  exit 0
fi
if [[ "$1" == "session" && "$2" == "remove" ]]; then
  rm -f "$TMPDIR/fake-vivi-pty-state-$3" "$TMPDIR/fake-vivi-pty-cmd-$3"
  exit 0
fi
if [[ "$1" == "terminal" && "$2" == "write" ]]; then
  echo "$4" >> "$TMPDIR/fake-vivi-pty-boot-$3"
  exit 0
fi
exit 1
''',
        )

    def install_fake_tmux(self):
        self.write_fake(
            "tmux",
            r'''
log="$TMPDIR/fake-tmux-log"
case "$1" in
  has-session) [[ -f "$TMPDIR/fake-tmux-session" ]] && exit 0 || exit 1 ;;
  new-session) touch "$TMPDIR/fake-tmux-session"; echo "new-session $*" >> "$log"; exit 0 ;;
  list-windows) echo "head-ceo"; exit 0 ;;
  new-window) echo "new-window $*" >> "$log"; exit 0 ;;
  display-message)
    [[ -f "$TMPDIR/fake-tmux-session" ]] || exit 1
    [[ "${FAKE_TMUX_TARGET_MISSING:-0}" == "1" ]] && exit 1
    echo "%1"; exit 0 ;;
  capture-pane) echo "›"; exit 0 ;;
  send-keys) echo "send-keys $*" >> "$log"; exit 0 ;;
  kill-window)
    echo "kill-window $*" >> "$log"
    [[ "${FAKE_TMUX_KILL_WINDOW_FAIL:-0}" == "1" ]] && exit 1
    exit 0 ;;
  kill-session) rm -f "$TMPDIR/fake-tmux-session"; echo "kill-session $*" >> "$log"; exit 0 ;;
esac
exit 0
''',
        )

    def test_vivi_pty_start_boot_stop(self):
        self.install_fake_vivi_pty()
        self.write_fleet({
            "fleet_id": "test",
            "head-ceo": {
                "agent": "pi",
                "mail_identity": "head-ceo",
                "cwd": str(self.root),
                "runtime": {
                    "kind": "vivi_pty",
                    "session_id": "test-head-ceo",
                    "socket": str(self.root / ".vivi" / "vivi-pty.sock"),
                    "driver": "pi",
                    "command": ["pi", "--model", "fake"],
                },
            },
        })
        rc = self.run_helper("--role", "head-ceo", "--boot", "hello", "start")
        self.assertEqual(rc.returncode, 0, rc.stderr + rc.stdout)
        self.assertIn("head-ceo", rc.stdout)
        boot = Path(os.environ.get("TMPDIR", "/tmp")) / "fake-vivi-pty-boot-test-head-ceo"
        self.assertIn("hello", boot.read_text(encoding="utf-8"))
        rc2 = self.run_helper("--role", "head-ceo", "stop")
        self.assertEqual(rc2.returncode, 0, rc2.stderr + rc2.stdout)

    def test_tmux_restart_uses_configured_role_window(self):
        self.install_fake_tmux()
        self.write_fleet({
            "fleet_id": "test",
            "tmux_layout": "session_per_fleet",
            "head-ceo": {
                "agent": "pi",
                "mail_identity": "head-ceo",
                "cwd": str(self.root),
                "tmux_session": "test",
                "tmux_window": "head-ceo",
                "tmux_target": "test:head-ceo.1",
                "agent_launch": "pi --model fake",
            },
        })
        rc = self.run_helper("--role", "head-ceo", "restart")
        self.assertEqual(rc.returncode, 0, rc.stderr + rc.stdout)
        log = (Path(os.environ.get("TMPDIR", "/tmp")) / "fake-tmux-log").read_text(encoding="utf-8")
        self.assertIn("new-session", log)
        self.assertIn("send-keys", log)

    def test_missing_role_window_never_kills_shared_session(self):
        self.install_fake_tmux()
        self.write_fleet({
            "fleet_id": "test",
            "tmux_layout": "session_per_fleet",
            "hands": {
                "hand-1": {
                    "agent": "pi",
                    "mail_identity": "hand-1",
                    "cwd": str(self.root),
                    "tmux_session": "test",
                    "tmux_window": "hand-1",
                    "tmux_target": "test:hand-1.1",
                    "agent_launch": "pi --model fake",
                },
            },
        })
        session = Path(os.environ.get("TMPDIR", "/tmp")) / "fake-tmux-session"
        log = Path(os.environ.get("TMPDIR", "/tmp")) / "fake-tmux-log"
        session.touch()
        os.environ["FAKE_TMUX_TARGET_MISSING"] = "1"
        try:
            rc = self.run_helper("--role", "hand-1", "stop")
        finally:
            os.environ.pop("FAKE_TMUX_TARGET_MISSING", None)
        self.assertEqual(rc.returncode, 0, rc.stderr + rc.stdout)
        self.assertTrue(session.exists(), "role stop must preserve the shared tmux session")
        self.assertNotIn("kill-session", log.read_text(encoding="utf-8") if log.exists() else "")
        self.assertIn("window already stopped", rc.stdout)

    def test_role_window_stop_failure_never_falls_back_to_shared_session(self):
        self.install_fake_tmux()
        self.write_fleet({
            "fleet_id": "test",
            "tmux_layout": "session_per_fleet",
            "hands": {
                "hand-1": {
                    "agent": "pi",
                    "mail_identity": "hand-1",
                    "cwd": str(self.root),
                    "tmux_session": "test",
                    "tmux_window": "hand-1",
                    "tmux_target": "test:hand-1.1",
                },
            },
        })
        session = Path(os.environ.get("TMPDIR", "/tmp")) / "fake-tmux-session"
        log = Path(os.environ.get("TMPDIR", "/tmp")) / "fake-tmux-log"
        session.touch()
        os.environ["FAKE_TMUX_KILL_WINDOW_FAIL"] = "1"
        try:
            rc = self.run_helper("--role", "hand-1", "stop")
        finally:
            os.environ.pop("FAKE_TMUX_KILL_WINDOW_FAIL", None)
        self.assertEqual(rc.returncode, 1)
        self.assertTrue(session.exists(), "failed role stop must preserve the shared tmux session")
        events = log.read_text(encoding="utf-8")
        self.assertIn("kill-window", events)
        self.assertNotIn("kill-session", events)

    def test_doctor_fails_stopped_vivi_pty(self):
        self.install_fake_vivi_pty()
        self.write_fleet({
            "fleet_id": "test",
            "head-cxo": {
                "agent": "pi",
                "runtime": {"kind": "vivi_pty", "session_id": "test-head-cxo", "command": ["pi"]},
            },
        })
        rc = self.run_helper("--role", "head-cxo", "doctor")
        self.assertEqual(rc.returncode, 1)
        self.assertIn("stopped", rc.stdout)

    def test_agent_launch_preferred_over_stale_runtime_command(self):
        """agent_launch wins so reinit cannot rebind plain pi from stale command."""
        self.install_fake_vivi_pty()
        wrapper = self.bin / "pi-head"
        wrapper.write_text("#!/usr/bin/env bash\nexec true\n", encoding="utf-8")
        wrapper.chmod(0o755)
        self.write_fleet({
            "fleet_id": "test",
            "head-ceo": {
                "agent": "pi",
                "mail_identity": "head-ceo",
                "cwd": str(self.root),
                "agent_launch": "%s --model good --approve" % wrapper,
                "runtime": {
                    "kind": "vivi_pty",
                    "session_id": "test-head-ceo",
                    "socket": str(self.root / ".vivi" / "vivi-pty.sock"),
                    "driver": "pi",
                    # Stale plain pi — must NOT be used when agent_launch is set
                    "command": ["pi", "--model", "stale"],
                },
            },
        })
        rc = self.run_helper("--role", "head-ceo", "start")
        self.assertEqual(rc.returncode, 0, rc.stderr + rc.stdout)
        cmd_path = Path(os.environ.get("TMPDIR", "/tmp")) / "fake-vivi-pty-cmd-test-head-ceo"
        stored = json.loads(cmd_path.read_text(encoding="utf-8"))
        self.assertEqual(stored[0], str(wrapper))
        self.assertIn("good", stored)
        self.assertNotIn("stale", stored)

    def test_reinit_removes_then_starts_with_desired_argv(self):
        self.install_fake_vivi_pty()
        self.write_fleet({
            "fleet_id": "test",
            "head-cto": {
                "agent": "pi",
                "agent_launch": "pi --model new --approve",
                "runtime": {
                    "kind": "vivi_pty",
                    "session_id": "test-head-cto",
                    "socket": str(self.root / ".vivi" / "vivi-pty.sock"),
                    "command": ["pi", "--model", "old"],
                },
            },
        })
        # Seed a running session with old command
        Path(os.environ.get("TMPDIR", "/tmp") + "/fake-vivi-pty-state-test-head-cto").write_text(
            "running", encoding="utf-8"
        )
        Path(os.environ.get("TMPDIR", "/tmp") + "/fake-vivi-pty-cmd-test-head-cto").write_text(
            '["pi","--model","old"]', encoding="utf-8"
        )
        rc = self.run_helper("--role", "head-cto", "reinit")
        self.assertEqual(rc.returncode, 0, rc.stderr + rc.stdout)
        stored = json.loads(
            Path(os.environ.get("TMPDIR", "/tmp") + "/fake-vivi-pty-cmd-test-head-cto").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("new", stored)
        self.assertNotIn("old", stored)


if __name__ == "__main__":
    unittest.main()
