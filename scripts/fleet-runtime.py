#!/usr/bin/env python3
"""Backend-neutral Fleet runtime lifecycle helper.

This helper owns the mechanical process lifecycle for configured Hand/Head
runtimes. It deliberately does not assign work, change posture, or mutate board
items. Use ``fleet-doorbell.sh`` for assignment-aware wakes after a runtime is
ready.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from fleet_common import (
    FleetScopeError,
    require_python,
    resolve_fleet_file,
    resolve_role,
    resolve_runtime_binding,
    role_names,
    run_cmd,
    which,
)


def _slot(fleet: Dict[str, Any], role: str) -> Dict[str, Any]:
    _, slot, _ = resolve_role(fleet, role)
    return slot


def _role_group(fleet: Dict[str, Any], role: str) -> str:
    _, _, group = resolve_role(fleet, role)
    return group


def _parse_selector(value: Optional[str], all_names: List[str], group: str, fleet: Dict[str, Any]) -> List[str]:
    if not value:
        return []
    candidates = [n for n in all_names if _role_group(fleet, n) == group]
    if value == "all":
        return candidates
    wanted = [part.strip() for part in value.split(",") if part.strip()]
    unknown = [name for name in wanted if name not in candidates]
    if unknown:
        raise FleetScopeError("unknown %s role(s): %s" % (group, ", ".join(unknown)))
    return wanted


def selected_roles(fleet: Dict[str, Any], args: argparse.Namespace) -> List[str]:
    names = role_names(fleet)
    result: List[str] = []
    for role in args.role or []:
        resolve_role(fleet, role)
        result.append(role)
    result.extend(_parse_selector(args.hands, names, "hand", fleet))
    result.extend(_parse_selector(args.heads, names, "head", fleet))
    seen = set()
    ordered = []
    for role in result:
        if role not in seen:
            seen.add(role)
            ordered.append(role)
    if not ordered:
        raise FleetScopeError("no roles selected (use --role, --hands, or --heads)")
    return ordered


def _vivi_pty_bin(fleet: Dict[str, Any]) -> str:
    return which("vivi-pty", fleet.get("tooling") if isinstance(fleet.get("tooling"), dict) else None, "vivi_pty") or shutil.which("vivi-pty") or "vivi-pty"


def _tmux_bin(fleet: Dict[str, Any]) -> str:
    tooling = fleet.get("tooling") if isinstance(fleet.get("tooling"), dict) else None
    return which("tmux", tooling, "tmux") or shutil.which("tmux") or "tmux"


def _launch_argv(slot: Dict[str, Any], binding: Dict[str, Any]) -> List[str]:
    """Desired process argv for a role.

    Canonical order:
      1. ``agent_launch`` when set (wrappers like pi-hand/pi-head live here)
      2. ``runtime.command`` for vivi_pty when agent_launch is absent

    Preferring agent_launch prevents reinit from reusing a stale plain-``pi``
    runtime.command after fleet.json launch policy was updated.
    """
    launch = str(slot.get("agent_launch") or "").strip()
    if launch:
        try:
            return shlex.split(launch)
        except ValueError:
            return [launch]
    runtime = slot.get("runtime") if isinstance(slot.get("runtime"), dict) else {}
    command = runtime.get("command")
    if binding.get("kind") == "vivi_pty" and isinstance(command, list) and command:
        return [str(part) for part in command]
    return []


def _render_cmd(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in argv)


def _session_command(inspect_payload: Dict[str, Any]) -> List[str]:
    cmd = inspect_payload.get("command")
    if isinstance(cmd, list):
        return [str(part) for part in cmd]
    return []


def vivi_status(fleet: Dict[str, Any], binding: Dict[str, Any]) -> Dict[str, Any]:
    bin_path = _vivi_pty_bin(fleet)
    socket = str(binding.get("socket") or "")
    session_id = str(binding.get("session") or binding.get("target") or "")
    rc, out = run_cmd([bin_path, "session", "diagnostic", session_id, "--socket", socket], timeout=5)
    if rc != 0:
        rc2, inspect = run_cmd([bin_path, "session", "inspect", session_id, "--socket", socket], timeout=5)
        if rc2 != 0:
            return {"state": "stopped", "exists": False, "detail": out or inspect}
        try:
            data = json.loads(inspect)
        except Exception:
            return {"state": "unknown", "exists": True, "detail": inspect}
        state = str(data.get("state") or "unknown")
        return {"state": state, "exists": state not in ("stopped", "exited"), "session": data}
    try:
        data = json.loads(out)
    except Exception:
        return {"state": "unknown", "exists": True, "detail": out}
    process_state = str(data.get("process_state") or (data.get("session") or {}).get("state") or "unknown")
    harness_state = str(data.get("harness_state") or "unknown")
    stopped = process_state in ("stopped", "exited")
    return {
        "state": "stopped" if stopped else harness_state,
        "process_state": process_state,
        "exists": not stopped,
        "confidence": data.get("confidence"),
        "evidence": data.get("evidence") or [],
    }


def ensure_vivi_daemon(fleet: Dict[str, Any], project: Path, socket: str) -> Tuple[bool, str]:
    bin_path = _vivi_pty_bin(fleet)
    rc, out = run_cmd([bin_path, "info", "--socket", socket], timeout=5)
    if rc == 0:
        return True, "daemon already running"
    Path(socket).parent.mkdir(parents=True, exist_ok=True)
    # Start detached without shell evaluation.
    try:
        import subprocess
        subprocess.Popen(
            [bin_path, "daemon", "--project", str(project), "--socket", socket],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        return False, str(exc)
    for _ in range(30):
        rc, _ = run_cmd([bin_path, "info", "--socket", socket], timeout=1)
        if rc == 0:
            return True, "daemon started"
        import time
        time.sleep(0.2)
    return False, "daemon failed to start"


def _vivi_start_args(
    bin_path: str,
    binding: Dict[str, Any],
    project: Path,
    session_id: str,
    socket: str,
    argv: Sequence[str],
) -> List[str]:
    args = [
        bin_path,
        "session",
        "start",
        session_id,
        "--driver",
        str(binding.get("driver") or binding.get("agent") or "generic"),
        "--cwd",
        str(binding.get("cwd") or project),
        "--socket",
        socket,
        "--",
    ]
    args.extend(list(argv))
    return args


def remove_vivi(fleet: Dict[str, Any], binding: Dict[str, Any]) -> Tuple[bool, str]:
    """Drop a vivi_pty session id (stop + no tombstone). Requires session.remove."""
    bin_path = _vivi_pty_bin(fleet)
    session_id = str(binding.get("session") or binding.get("target") or "")
    socket = str(binding.get("socket") or "")
    if not session_id:
        return False, "missing session id"
    # Prefer remove; fall back to stop-only when binary is older.
    rc, out = run_cmd([bin_path, "session", "remove", session_id, "--socket", socket], timeout=10)
    if rc == 0:
        return True, "removed"
    # Older vivi-pty: no session.remove subcommand.
    if "unrecognized" in (out or "").lower() or "unexpected" in (out or "").lower() or "error:" in (out or "").lower():
        rc2, out2 = run_cmd([bin_path, "session", "stop", session_id, "--socket", socket], timeout=10)
        if rc2 == 0:
            return False, "remove unsupported; stopped only (tombstone remains — upgrade vivi-pty)"
        return False, out or out2 or "remove failed"
    # Not found is ok for reinit.
    if "unknown session" in (out or "").lower() or "not found" in (out or "").lower():
        return True, "absent"
    return False, out or "remove failed"


def start_vivi(
    fleet: Dict[str, Any],
    project: Path,
    role: str,
    binding: Dict[str, Any],
    slot: Dict[str, Any],
    *,
    rebind: bool = False,
) -> Tuple[bool, str]:
    bin_path = _vivi_pty_bin(fleet)
    socket = str(binding.get("socket") or project / ".vivi" / "vivi-pty.sock")
    session_id = str(binding.get("session") or binding.get("target") or role)
    ok, msg = ensure_vivi_daemon(fleet, project, socket)
    if not ok:
        return False, msg
    argv = _launch_argv(slot, binding)
    if not argv:
        return False, "missing agent_launch/runtime.command"

    status = vivi_status(fleet, binding)
    if status.get("exists") and not rebind:
        return True, "already running"

    rc_i, inspect_out = run_cmd([bin_path, "session", "inspect", session_id, "--socket", socket], timeout=5)
    stored: List[str] = []
    if rc_i == 0:
        try:
            stored = _session_command(json.loads(inspect_out))
        except Exception:
            stored = []

    # Running or stopped tombstone with matching argv → restart preserves binding.
    if rc_i == 0 and stored == argv and not rebind:
        rc, out = run_cmd([bin_path, "session", "restart", session_id, "--socket", socket], timeout=15)
        return rc == 0, "restarted" if rc == 0 else out

    # Need a clean start with desired argv: drop id when present.
    if rc_i == 0:
        ok_rm, rm_msg = remove_vivi(fleet, binding)
        if not ok_rm:
            # Last resort: restart only works if command is unchanged.
            if stored == argv:
                rc, out = run_cmd([bin_path, "session", "restart", session_id, "--socket", socket], timeout=15)
                return rc == 0, "restarted (remove unavailable)" if rc == 0 else out
            return False, (
                "cannot rebind session command (session.remove unavailable or failed: %s); "
                "upgrade vivi-pty or recycle the daemon" % rm_msg
            )

    args = _vivi_start_args(bin_path, binding, project, session_id, socket, argv)
    rc, out = run_cmd(args, timeout=15)
    if rc != 0:
        return False, out or "start failed"
    label = "rebound" if rebind or (stored and stored != argv) else "started"
    return True, label


def stop_vivi(fleet: Dict[str, Any], binding: Dict[str, Any]) -> Tuple[bool, str]:
    bin_path = _vivi_pty_bin(fleet)
    session_id = str(binding.get("session") or binding.get("target") or "")
    socket = str(binding.get("socket") or "")
    rc, out = run_cmd([bin_path, "session", "stop", session_id, "--socket", socket], timeout=10)
    return rc == 0, "stopped" if rc == 0 else out


def boot_vivi(fleet: Dict[str, Any], binding: Dict[str, Any], boot: str) -> Tuple[bool, str]:
    if not boot:
        return True, "no boot"
    bin_path = _vivi_pty_bin(fleet)
    session_id = str(binding.get("session") or binding.get("target") or "")
    socket = str(binding.get("socket") or "")
    rc, out = run_cmd([bin_path, "terminal", "write", session_id, boot, "--enter", "--socket", socket], timeout=10)
    return rc == 0, out or "boot sent"


def tmux_target_exists(tmux: str, target: str) -> bool:
    rc, _ = run_cmd([tmux, "display-message", "-p", "-t", target, "#{pane_id}"], timeout=5)
    return rc == 0


def tmux_status(fleet: Dict[str, Any], binding: Dict[str, Any]) -> Dict[str, Any]:
    tmux = _tmux_bin(fleet)
    session = str(binding.get("session") or "")
    target = str(binding.get("target") or "")
    rc, _ = run_cmd([tmux, "has-session", "-t", session], timeout=5)
    if rc != 0:
        return {"state": "stopped", "exists": False}
    if not tmux_target_exists(tmux, target):
        return {"state": "stopped", "exists": False, "detail": "target missing"}
    rc2, tail = run_cmd([tmux, "capture-pane", "-t", target, "-p", "-S", "-12"], timeout=5)
    return {"state": "present" if rc2 == 0 else "unknown", "exists": True, "tail": tail[-1000:]}


def ensure_tmux_topology(fleet: Dict[str, Any], binding: Dict[str, Any]) -> Tuple[bool, str]:
    tmux = _tmux_bin(fleet)
    session = str(binding.get("session") or "")
    window = str(binding.get("window") or "")
    cwd = str(binding.get("cwd") or ".")
    rc, _ = run_cmd([tmux, "has-session", "-t", session], timeout=5)
    if rc != 0:
        args = [tmux, "new-session", "-d", "-s", session]
        if window:
            args.extend(["-n", window])
        args.extend(["-c", cwd])
        rc2, out = run_cmd(args, timeout=10)
        return rc2 == 0, out or "session created"
    if window:
        rcw, windows = run_cmd([tmux, "list-windows", "-t", session, "-F", "#{window_name}"], timeout=5)
        if rcw == 0 and window not in set(windows.splitlines()):
            rc2, out = run_cmd([tmux, "new-window", "-d", "-t", session, "-n", window, "-c", cwd], timeout=10)
            return rc2 == 0, out or "window created"
    return True, "topology present"


def start_tmux(fleet: Dict[str, Any], binding: Dict[str, Any], slot: Dict[str, Any], force: bool = False) -> Tuple[bool, str]:
    tmux = _tmux_bin(fleet)
    existed_before = tmux_status(fleet, binding).get("exists") is True
    ok, msg = ensure_tmux_topology(fleet, binding)
    if not ok:
        return False, msg
    target = str(binding.get("target") or "")
    if not tmux_target_exists(tmux, target):
        return False, "target missing after topology create: %s" % target
    argv = _launch_argv(slot, binding)
    if not argv:
        return True, "topology ready; no launch command configured"
    if existed_before and not force:
        # We cannot portably know whether a shell already hosts an agent; do not stack.
        return True, "target exists; launch not stacked (use --force to send command)"
    rc, out = run_cmd([tmux, "send-keys", "-t", target, "-l", "--", _render_cmd(argv)], timeout=10)
    if rc != 0:
        return False, out
    rc2, out2 = run_cmd([tmux, "send-keys", "-t", target, "Enter"], timeout=10)
    return rc2 == 0, out2 or "launch sent"


def stop_tmux(fleet: Dict[str, Any], binding: Dict[str, Any]) -> Tuple[bool, str]:
    tmux = _tmux_bin(fleet)
    session = str(binding.get("session") or "")
    window = str(binding.get("window") or "")
    target = "%s:%s" % (session, window) if window else session
    rc, out = run_cmd([tmux, "has-session", "-t", session], timeout=5)
    if rc != 0:
        return True, "already stopped"
    if window:
        rc2, out2 = run_cmd([tmux, "kill-window", "-t", target], timeout=10)
        if rc2 == 0:
            return True, out2 or "window stopped"
    rc3, out3 = run_cmd([tmux, "kill-session", "-t", session], timeout=10)
    return rc3 == 0, out3 or "session stopped"


def boot_tmux(fleet: Dict[str, Any], binding: Dict[str, Any], boot: str) -> Tuple[bool, str]:
    if not boot:
        return True, "no boot"
    tmux = _tmux_bin(fleet)
    target = str(binding.get("target") or "")
    rc, out = run_cmd([tmux, "send-keys", "-t", target, "-l", "--", boot], timeout=10)
    if rc != 0:
        return False, out
    rc2, out2 = run_cmd([tmux, "send-keys", "-t", target, "Enter"], timeout=10)
    return rc2 == 0, out2 or "boot sent"


def role_status(fleet: Dict[str, Any], project: Path, role: str) -> Dict[str, Any]:
    binding = resolve_runtime_binding(fleet, role, project=project)
    if binding["kind"] == "vivi_pty":
        status = vivi_status(fleet, binding)
    else:
        status = tmux_status(fleet, binding)
    return {"role": role, "kind": binding["kind"], "target": binding.get("target"), **status}


def act_on_role(fleet: Dict[str, Any], project: Path, role: str, action: str, boot: str, force: bool) -> Dict[str, Any]:
    slot = _slot(fleet, role)
    binding = resolve_runtime_binding(fleet, role, project=project)
    kind = str(binding.get("kind"))
    ok = True
    msg = ""
    if action == "status":
        status = role_status(fleet, project, role)
        # Surface launch drift for operators (doctor/status).
        if kind == "vivi_pty":
            desired = _launch_argv(slot, binding)
            status["desired_command"] = desired
            bin_path = _vivi_pty_bin(fleet)
            session_id = str(binding.get("session") or binding.get("target") or "")
            socket = str(binding.get("socket") or "")
            rc, inspect_out = run_cmd(
                [bin_path, "session", "inspect", session_id, "--socket", socket], timeout=5
            )
            if rc == 0:
                try:
                    stored = _session_command(json.loads(inspect_out))
                except Exception:
                    stored = []
                status["stored_command"] = stored
                if desired and stored and desired != stored:
                    status["command_drift"] = True
                    status["ok"] = False
                    status["message"] = "command drift: reinit to rebind agent_launch"
        return status
    if action == "start":
        ok, msg = (
            start_vivi(fleet, project, role, binding, slot, rebind=False)
            if kind == "vivi_pty"
            else start_tmux(fleet, binding, slot, force=force)
        )
    elif action == "stop":
        ok, msg = stop_vivi(fleet, binding) if kind == "vivi_pty" else stop_tmux(fleet, binding)
    elif action in ("restart", "reinit"):
        # reinit always rebinds to agent_launch; restart reuses session when argv matches.
        rebind = action == "reinit" or force
        if kind == "vivi_pty":
            ok, msg = start_vivi(fleet, project, role, binding, slot, rebind=rebind)
            if not ok and rebind:
                # Explicit stop+rebind path if start_vivi could not replace a live session.
                stop_vivi(fleet, binding)
                ok, msg = start_vivi(fleet, project, role, binding, slot, rebind=True)
        else:
            ok, msg = stop_tmux(fleet, binding)
            if ok:
                ok, msg = start_tmux(fleet, binding, slot, force=True)
    else:
        raise FleetScopeError("unknown action: %s" % action)
    if ok and boot and action in ("start", "restart", "reinit"):
        ok, msg = boot_vivi(fleet, binding, boot) if kind == "vivi_pty" else boot_tmux(fleet, binding, boot)
    status = role_status(fleet, project, role)
    status.update({"ok": ok, "message": msg})
    return status


def load_boot(args: argparse.Namespace) -> str:
    if args.boot_file:
        return Path(args.boot_file).read_text(encoding="utf-8")
    return args.boot or ""


def main(argv: Optional[Sequence[str]] = None) -> int:
    require_python()
    ap = argparse.ArgumentParser(description="Backend-neutral Fleet runtime lifecycle helper")
    ap.add_argument("--project", "-p", required=True, help="fleet project root")
    ap.add_argument("--fleet", "-f", default=None, help="logical fleet id")
    ap.add_argument("--fleet-file", default=None, help="explicit fleet.json path")
    ap.add_argument("--role", action="append", default=None, help="role to operate on; repeatable")
    ap.add_argument("--hands", default=None, help='"all" or comma-separated hand roles')
    ap.add_argument("--heads", default=None, help='"all" or comma-separated head roles')
    ap.add_argument("--json", action="store_true", help="emit JSON")
    ap.add_argument("--force", action="store_true", help="allow tmux launch command to be sent into an existing target")
    ap.add_argument("--boot", default="", help="boot/pointer text to send after start/restart")
    ap.add_argument("--boot-file", default=None, help="file containing boot/pointer text")
    ap.add_argument("action", choices=["status", "start", "stop", "restart", "reinit", "doctor"])
    args = ap.parse_args(argv)

    try:
        _, fleet = resolve_fleet_file(args.project, args.fleet, args.fleet_file)
        project = Path(args.project).expanduser().resolve()
        roles = selected_roles(fleet, args)
        boot = load_boot(args)
        action = "status" if args.action == "doctor" else args.action
        results = [act_on_role(fleet, project, role, action, boot, args.force) for role in roles]
    except FleetScopeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    except OSError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    bad = any(r.get("ok", True) is False for r in results)
    if args.action == "doctor":
        for r in results:
            if r.get("state") in ("stopped", "failed") or r.get("process_state") in ("stopped", "exited"):
                r["ok"] = False
        bad = bad or any(r.get("ok", True) is False for r in results)
    if args.json:
        print(json.dumps({"ok": not bad, "roles": results}, indent=2))
    else:
        for r in results:
            status = r.get("process_state") or r.get("state")
            ok = "ok" if r.get("ok", True) is not False else "FAIL"
            print("%s %s kind=%s state=%s target=%s %s" % (ok, r.get("role"), r.get("kind"), status, r.get("target"), r.get("message", "")))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
