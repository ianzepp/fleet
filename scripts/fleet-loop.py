#!/usr/bin/env python3
"""tmux-backed Mind loop injector for harnesses without native scheduling.

This helper is a fallback scheduler. It periodically sends a FLEET_CYCLE
message into an operator/Mind tmux pane. The Mind still owns the real cycle:
sensors, dispositions, baseline bump, wakes, and reporting.

State lives at <project>/.vivi/fleet-loop.json. Stop kills only the recorded
loop process group.

Examples:
  fleet-loop.py --project /repo start 5m --target operator:node.1
  fleet-loop.py --project /repo status
  fleet-loop.py --project /repo stop

Exit: 0 ok · 1 runtime/config error · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    FleetScopeError,
    add_fleet_scope_arguments,
    ensure_dict,
    load_json,
    now_iso,
    require_python,
    resolve_fleet_file,
    run_cmd,
    save_json,
    which,
)

require_python()


DEFAULT_INTERVAL_SEC = 300
MIN_INTERVAL_SEC = 60
DEFAULT_TARGET = "current"


def parse_duration(value: Optional[str], *, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    units = [
        ("seconds", 1), ("second", 1), ("secs", 1), ("sec", 1), ("s", 1),
        ("minutes", 60), ("minute", 60), ("mins", 60), ("min", 60), ("m", 60),
        ("hours", 3600), ("hour", 3600), ("hrs", 3600), ("hr", 3600), ("h", 3600),
    ]
    for suffix, multiplier in units:
        if text.endswith(suffix):
            number = text[: -len(suffix)].strip()
            if not number:
                raise ValueError("missing duration value: %r" % value)
            return int(float(number) * multiplier)
    return int(float(text))


def project_root(args: argparse.Namespace) -> Path:
    try:
        path, _fleet = resolve_fleet_file(args.project, args.fleet, args.fleet_file)
    except FleetScopeError as exc:
        raise SystemExit("error: %s" % exc)
    return path.parent.parent


def state_path(project: Path) -> Path:
    return project / ".vivi" / "fleet-loop.json"


def log_path(project: Path) -> Path:
    return project / ".vivi" / "fleet-loop.log"


def pid_alive(pid: Any) -> bool:
    try:
        n = int(pid)
    except (TypeError, ValueError):
        return False
    if n <= 0:
        return False
    try:
        os.kill(n, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def load_state(project: Path) -> Dict[str, Any]:
    data = load_json(state_path(project), default={})
    return data if isinstance(data, dict) else {}


def resolve_target(tmux_bin: str, requested: str) -> str:
    if requested and requested != DEFAULT_TARGET:
        return requested
    rc, out = run_cmd(
        [tmux_bin, "display-message", "-p", "#{session_name}:#{window_name}.#{pane_index}"],
        timeout=5,
    )
    if rc != 0 or not out.strip():
        raise RuntimeError(
            "cannot infer current tmux pane; pass --target <session:window.pane>"
        )
    return out.strip().splitlines()[-1].strip()


def fleet_slug(project: Path, fleet: Dict[str, Any]) -> str:
    for key in ("fleet_id", "mailspace"):
        value = fleet.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return project.name


def build_payload(project: Path, fleet: Dict[str, Any], args: argparse.Namespace) -> str:
    if args.payload:
        payload = args.payload.replace("{project}", str(project)).replace(
            "{fleet}", fleet_slug(project, fleet)
        )
        if not payload.startswith("FLEET_CYCLE"):
            raise RuntimeError("custom payload must start with FLEET_CYCLE")
        return payload.rstrip("\n")
    slug = fleet_slug(project, fleet)
    if args.fleets:
        first = "FLEET_CYCLE fleets=%s" % args.fleets
    else:
        first = "FLEET_CYCLE fleets=%s" % slug
    return "%s\nRoots:\n  %s: %s" % (first, slug, project)


def send_payload(tmux_bin: str, target: str, payload: str) -> None:
    rc, out = run_cmd([tmux_bin, "send-keys", "-t", target, "-l", "--", payload], timeout=10)
    if rc != 0:
        raise RuntimeError("tmux send-keys text failed: %s" % out)
    rc, out = run_cmd([tmux_bin, "send-keys", "-t", target, "Enter"], timeout=10)
    if rc != 0:
        raise RuntimeError("tmux send-keys Enter failed: %s" % out)


def append_log(project: Path, line: str) -> None:
    path = log_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write("%s %s\n" % (now_iso(), line))


def cmd_run(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    tmux_bin = args.tmux_bin or which("tmux")
    if not tmux_bin:
        print("error: tmux not found", file=sys.stderr)
        return 1

    interval = int(args.interval_sec)
    max_cycles = int(args.max_cycles) if args.max_cycles is not None else None
    stop_after = int(args.stop_after_sec) if args.stop_after_sec is not None else None
    deadline = time.time() + stop_after if stop_after else None
    cycle = 0
    append_log(project, "loop run pid=%s target=%s interval=%ss" % (os.getpid(), args.target, interval))

    if args.immediate:
        try:
            send_payload(tmux_bin, args.target, args.payload)
            cycle += 1
            append_log(project, "sent cycle=%s immediate" % cycle)
        except Exception as exc:
            append_log(project, "send failed immediate: %s" % exc)

    while True:
        if max_cycles is not None and cycle >= max_cycles:
            append_log(project, "loop exit max_cycles=%s" % max_cycles)
            return 0
        if deadline is not None and time.time() >= deadline:
            append_log(project, "loop exit duration=%ss" % stop_after)
            return 0
        sleep_for = interval
        if deadline is not None:
            sleep_for = max(1, min(sleep_for, int(deadline - time.time())))
        time.sleep(sleep_for)
        if deadline is not None and time.time() >= deadline and sleep_for < interval:
            append_log(project, "loop exit duration=%ss" % stop_after)
            return 0
        try:
            send_payload(tmux_bin, args.target, args.payload)
            cycle += 1
            append_log(project, "sent cycle=%s" % cycle)
        except Exception as exc:
            append_log(project, "send failed: %s" % exc)


def cmd_start(args: argparse.Namespace) -> int:
    project = project_root(args)
    fleet_path, fleet = resolve_fleet_file(project, args.fleet, args.fleet_file)
    existing = load_state(project)
    if pid_alive(existing.get("pid")):
        print(
            "error: fleet loop already running pid=%s target=%s"
            % (existing.get("pid"), existing.get("target")),
            file=sys.stderr,
        )
        return 1

    tmux_bin = args.tmux_bin or which("tmux")
    if not tmux_bin:
        print("error: tmux not found", file=sys.stderr)
        return 1
    try:
        target = resolve_target(tmux_bin, args.target)
        interval = parse_duration(args.interval, default=DEFAULT_INTERVAL_SEC) or DEFAULT_INTERVAL_SEC
        stop_after = parse_duration(args.duration, default=None)
        if interval < MIN_INTERVAL_SEC and not args.allow_short_interval:
            print("error: interval must be >= %ss (use --allow-short-interval for tests)" % MIN_INTERVAL_SEC, file=sys.stderr)
            return 2
        payload = build_payload(project, fleet, args)
    except (RuntimeError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--project", str(project),
        "_run",
        "--target", target,
        "--interval-sec", str(interval),
        "--payload", payload,
    ]
    if args.max_cycles is not None:
        cmd += ["--max-cycles", str(args.max_cycles)]
    if stop_after is not None:
        cmd += ["--stop-after-sec", str(stop_after)]
    if args.immediate:
        cmd.append("--immediate")
    if args.tmux_bin:
        cmd += ["--tmux-bin", args.tmux_bin]

    log_fh = log_path(project).open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            cwd=str(project),
            start_new_session=True,
            close_fds=True,
        )
    finally:
        log_fh.close()

    state = {
        "version": 1,
        "pid": proc.pid,
        "project": str(project),
        "fleet_file": str(fleet_path),
        "fleet_id": fleet_slug(project, fleet),
        "target": target,
        "interval_sec": interval,
        "started_at": now_iso(),
        "payload": payload,
        "max_cycles": args.max_cycles,
        "duration_sec": stop_after,
        "log": str(log_path(project)),
        "script": str(Path(__file__).resolve()),
    }
    save_json(state_path(project), state)
    append_log(project, "loop start pid=%s target=%s interval=%ss" % (proc.pid, target, interval))
    print(json.dumps({"ok": True, "started": state}, indent=2))
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    project = project_root(args)
    path = state_path(project)
    state = load_state(project)
    pid = state.get("pid")
    if not pid_alive(pid):
        if path.exists() and args.clear_stale:
            path.unlink()
            print(json.dumps({"ok": True, "stopped": False, "cleared_stale": True}, indent=2))
            return 0
        print(json.dumps({"ok": True, "stopped": False, "reason": "not running"}, indent=2))
        return 0
    try:
        os.killpg(int(pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    except Exception as exc:
        print("error: failed to stop pid %s: %s" % (pid, exc), file=sys.stderr)
        return 1
    time.sleep(0.3)
    if pid_alive(pid):
        try:
            os.killpg(int(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    if path.exists():
        path.unlink()
    append_log(project, "loop stop pid=%s" % pid)
    print(json.dumps({"ok": True, "stopped": True, "pid": pid}, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project = project_root(args)
    state = load_state(project)
    running = pid_alive(state.get("pid"))
    out = {
        "ok": True,
        "running": running,
        "state_file": str(state_path(project)),
        "state": state,
    }
    print(json.dumps(out, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="tmux-backed FLEET_CYCLE injector")
    add_fleet_scope_arguments(p, required_project=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("start", help="start a background tmux injector")
    s.add_argument("interval", nargs="?", default="5m", help="cycle interval, e.g. 5m, 10m, 300s")
    s.add_argument("--target", default=DEFAULT_TARGET, help="tmux pane target; default=current pane")
    s.add_argument("--duration", default=None, help="optional total runtime, e.g. 2h")
    s.add_argument("--max-cycles", type=int, default=None, help="optional stop after N sends")
    s.add_argument("--immediate", action="store_true", help="send one FLEET_CYCLE immediately")
    s.add_argument("--payload", default=None, help="custom FLEET_CYCLE payload; {project}/{fleet} expanded")
    s.add_argument("--fleets", default=None, help="override fleets= slug list on generated first line")
    s.add_argument("--tmux-bin", default=None, help="tmux binary override")
    s.add_argument("--allow-short-interval", action="store_true", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_start)

    t = sub.add_parser("stop", help="stop the recorded background loop")
    t.add_argument("--clear-stale", action="store_true", help="remove stale state when PID is not running")
    t.set_defaults(func=cmd_stop)

    q = sub.add_parser("status", help="show loop state")
    q.set_defaults(func=cmd_status)

    r = sub.add_parser("_run", help=argparse.SUPPRESS)
    r.add_argument("--target", required=True)
    r.add_argument("--interval-sec", required=True, type=int)
    r.add_argument("--payload", required=True)
    r.add_argument("--max-cycles", type=int, default=None)
    r.add_argument("--stop-after-sec", type=int, default=None)
    r.add_argument("--immediate", action="store_true")
    r.add_argument("--tmux-bin", default=None)
    r.set_defaults(func=cmd_run)
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
