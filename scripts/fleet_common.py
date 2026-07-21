"""Shared portability helpers for fleet Python scripts.

Target: Python 3.9+ on macOS and Linux. No third-party deps.
"""
from __future__ import annotations

import json
import os
import argparse
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

MIN_PY: Tuple[int, int] = (3, 9)
PathLike = Union[str, Path]


class FleetScopeError(ValueError):
    """A fleet project, identity, or role cannot be resolved safely."""


def require_python(min_version: Tuple[int, int] = MIN_PY) -> None:
    """Exit 2 if the interpreter is too old."""
    if sys.version_info < min_version:
        need = "%d.%d" % (min_version[0], min_version[1])
        have = "%d.%d.%d" % sys.version_info[:3]
        sys.stderr.write(
            "fleet: python >= %s required (running %s via %s)\n"
            % (need, have, sys.executable)
        )
        sys.exit(2)


def now_iso() -> str:
    """UTC timestamp as YYYY-MM-DDTHH:MM:SSZ (no microseconds)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_to_epoch(value: Optional[str]) -> int:
    """Parse ISO-8601 (with or without trailing Z) to unix epoch seconds.

    Python < 3.11 rejects trailing Z on fromisoformat; always normalize.
    Returns 0 on empty/unparseable input.
    """
    if not value:
        return 0
    s = str(value).strip()
    if not s:
        return 0
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def read_text(path: PathLike) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text_atomic(path: PathLike, text: str) -> None:
    """Write text atomically (temp file in same dir + os.replace)."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".%s." % dest.name,
        suffix=".tmp",
        dir=str(dest.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, dest)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_json(path: PathLike, default: Optional[Any] = None) -> Any:
    """Load JSON from path; missing/invalid file returns default (or {})."""
    fallback = {} if default is None else default
    p = Path(path)
    if not p.is_file():
        return fallback
    try:
        return json.loads(read_text(p))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return fallback


def save_json(path: PathLike, data: Any) -> None:
    write_text_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def which(
    name: str,
    tooling: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Optional[str]:
    """Resolve a binary: optional fleet tooling override, then PATH."""
    if tooling and key:
        block = tooling.get(key) or {}
        if isinstance(block, dict):
            binary = block.get("binary")
            if binary and Path(binary).is_file() and os.access(binary, os.X_OK):
                return str(binary)
    return shutil.which(name)


def run_cmd(
    cmd: Sequence[str],
    timeout: float = 30.0,
    cwd: Optional[PathLike] = None,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str]:
    """Run a command; return (rc, combined utf-8 text). Never raises for rc != 0."""
    try:
        proc = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd else None,
            env=env,
        )
        out = proc.stdout or ""
        if proc.stderr and proc.returncode:
            if out and not out.endswith("\n"):
                out += "\n"
            out += proc.stderr
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "timeout: %s" % " ".join(cmd)
    except FileNotFoundError:
        return 127, "missing: %s" % (cmd[0] if cmd else "?")
    except OSError as exc:
        return 126, "os error: %s" % exc


def ensure_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def fleet_id_of(fleet: Dict[str, Any], project: Optional[PathLike] = None) -> str:
    """Return the configured logical fleet ID, with the documented fallback."""
    for key in ("fleet_id", "mailspace"):
        value = fleet.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if project is not None:
        return Path(project).expanduser().resolve().name
    return ""


def resolve_fleet_file(
    project: PathLike,
    fleet_id: Optional[str] = None,
    fleet_file: Optional[PathLike] = None,
) -> Tuple[Path, Dict[str, Any]]:
    """Resolve and validate the fleet overlay selected by standard flags.

    ``--fleet`` is a logical ID. ``--fleet-file`` is the only path override.
    The project remains the durability boundary and is always required by
    callers even when a file override is used.

    fleet.json is deprecated. When absent, builds a synthetic fleet dict
    from Vivi role records and mailspace.
    """
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise FleetScopeError("project is not a directory: %s" % root)
    path = (
        Path(fleet_file).expanduser().resolve()
        if fleet_file
        else root / ".vivi" / "fleet.json"
    )
    if path.is_file():
        data = load_json(path, default=None)
        if not isinstance(data, dict):
            raise FleetScopeError("fleet.json must contain a JSON object: %s" % path)
        actual = fleet_id_of(data, root)
        if fleet_id and fleet_id != actual:
            raise FleetScopeError(
                "fleet ID mismatch: requested %r, configured %r (%s)"
                % (fleet_id, actual, path)
            )
        return path, data

    # fleet.json absent — build from Vivi
    data = build_fleet_from_vivi(root)
    if fleet_id and fleet_id != data.get("fleet_id", ""):
        raise FleetScopeError(
            "fleet ID mismatch: requested %r, configured %r"
            % (fleet_id, data.get("fleet_id", ""))
        )
    return path, data


def build_fleet_from_vivi(root: Path) -> Dict[str, Any]:
    """Build a synthetic fleet dict from Vivi role records and mailspace.

    Called when fleet.json is absent. Derives roster, identity, and defaults
    from Vivi-native surfaces.
    """
    project_str = str(root)
    mailspace = _vivi_mailspace_name(root)
    fleet_id = mailspace or root.name

    fleet: Dict[str, Any] = {
        "version": 3,
        "project": project_str,
        "mailspace": mailspace,
        "fleet_id": fleet_id,
        "mind_inbox": "mind",
        "operator_inbox": "operator",
        "head_report_inbox": "mind",
        "fleet_posture": {"mode": "standby"},
        "steward": {"enabled": False},
        "mind_loop": {"interval_sec": 900},
        "hands": {},
        "heads": {},
    }

    roles = _vivi_role_list(root)
    for role in roles:
        name = role.get("name", "")
        if not name:
            continue
        kind = role.get("kind") or ""
        entry: Dict[str, Any] = {
            "mail_identity": name,
            "cwd": project_str,
            "agent": role.get("provider") or "unknown",
            "agent_model": role.get("model") or "",
            "thinking": role.get("thinking") or "",
            "harness": role.get("harness") or "subagent",
        }
        if kind == "hand":
            fleet["hands"][name] = entry
        elif kind == "head":
            fleet["heads"][name] = entry
        elif name.startswith("hand-") or name.startswith("auditor-") or name.startswith("planner-"):
            fleet["hands"][name] = entry
        elif name.startswith("head-"):
            fleet["heads"][name] = entry

    return fleet


def _vivi_role_list(root: Path) -> List[Dict[str, Any]]:
    """Get role list from Vivi; return [] on failure."""
    rc, out = run_cmd(
        ["vivi", "role", "list", "--project", str(root), "--json"],
        timeout=15.0,
    )
    if rc != 0 or not out.strip():
        return []
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, ValueError):
        return []


def _vivi_mailspace_name(root: Path) -> str:
    """Get mailspace name from Vivi; fall back to directory name."""
    rc, out = run_cmd(
        ["vivi", "mailspace", "status", "--project", str(root), "--json"],
        timeout=15.0,
    )
    if rc == 0 and out.strip():
        try:
            data = json.loads(out)
            name = data.get("name") or data.get("mailspace")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except (json.JSONDecodeError, ValueError):
            pass
    return root.name


def add_fleet_scope_arguments(
    parser: argparse.ArgumentParser,
    *,
    required_project: bool = True,
    include_role: bool = False,
) -> None:
    """Add the shared logical fleet scope flags to a Python helper parser."""
    parser.add_argument(
        "--project", "-p", required=required_project,
        help="fleet project root",
    )
    parser.add_argument(
        "--fleet", "-f", default=None,
        help="logical fleet ID; validate against fleet.json",
    )
    parser.add_argument(
        "--fleet-file", default=None,
        help="explicit fleet.json path override",
    )
    if include_role:
        parser.add_argument(
            "--role", action="append", default=None,
            help="logical Hand/Head role; repeatable",
        )


def role_names(fleet: Dict[str, Any]) -> List[str]:
    """Return all configured Hand/Head role keys in stable order."""
    names = set()
    for block_name in ("hands", "hunters", "heads"):
        block = fleet.get(block_name)
        if isinstance(block, dict):
            names.update(str(key) for key, value in block.items() if isinstance(value, dict))
    names.update(
        str(key) for key, value in fleet.items()
        if isinstance(key, str) and key.startswith("head-") and isinstance(value, dict)
    )
    return sorted(names)


def resolve_role(fleet: Dict[str, Any], role: str) -> Tuple[str, Dict[str, Any], str]:
    """Resolve a logical role to its config block and role group."""
    if not isinstance(role, str) or not role.strip():
        raise FleetScopeError("role is required")
    name = role.strip()
    hands = fleet.get("hands") if isinstance(fleet.get("hands"), dict) else {}
    hunters = fleet.get("hunters") if isinstance(fleet.get("hunters"), dict) else {}
    heads = fleet.get("heads") if isinstance(fleet.get("heads"), dict) else {}
    for group, block in (("hand", hands), ("hand", hunters), ("head", heads)):
        value = block.get(name)
        if isinstance(value, dict):
            return name, value, group
    value = fleet.get(name)
    if name.startswith("head-") and isinstance(value, dict):
        return name, value, "head"
    raise FleetScopeError(
        "unknown role %r (known roles: %s)" % (name, ", ".join(role_names(fleet)) or "none")
    )


def _tmux_parts(target: str) -> Tuple[str, str, str]:
    """Split a tmux target into session, window, and pane components."""
    # Strip a leading exact-match marker if present (tmux `=session`).
    cleaned = target[1:] if target.startswith("=") else target
    match = re.match(r"^([^:]+):([^\.]+)(?:\.(.+))?$", cleaned)
    if not match:
        return cleaned, "", ""
    return match.group(1), match.group(2), match.group(3) or ""


def exact_tmux_session(session: str) -> str:
    """Return a tmux session token that matches only that name.

    tmux treats bare session names as prefixes, so ``swarm`` matches
    ``swarm-cli``. Prefix with ``=`` for exact match (tmux 2.1+).
    Do **not** use this for ``new-session -s`` (that sets the name).
    """
    name = str(session or "").strip()
    if not name:
        return name
    if name.startswith("="):
        return name
    return "=" + name


def exact_tmux_target(target: str) -> str:
    """Exact-match the session portion of a ``session:window.pane`` target."""
    t = str(target or "").strip()
    if not t:
        return t
    if t.startswith("="):
        return t
    if ":" in t:
        session, rest = t.split(":", 1)
        return "%s:%s" % (exact_tmux_session(session), rest)
    return exact_tmux_session(t)


# How Mind prepares a Hand/Head agent session when starting a *new* work item.
# See references/runtime-config.md § assignment_mode.
ASSIGNMENT_MODES = frozenset({"new", "compact", "continue", "restart"})


def resolve_assignment_mode(slot: Dict[str, Any]) -> str:
    """Resolve per-role session policy for a new assignment.

    Canonical field: ``assignment_mode`` ∈ {new, compact, continue, restart}.

    Legacy: ``clean_slate_per_assignment: true`` → ``new``;
    ``false`` → ``continue``. Unset defaults to ``continue`` (pointer into the
    existing session; historical Hand default).
    """
    raw = slot.get("assignment_mode")
    if raw is not None and str(raw).strip() != "":
        mode = str(raw).strip().lower()
        if mode not in ASSIGNMENT_MODES:
            raise FleetScopeError(
                "assignment_mode must be one of %s, got %r"
                % (sorted(ASSIGNMENT_MODES), raw)
            )
        return mode
    legacy = slot.get("clean_slate_per_assignment")
    if legacy is True:
        return "new"
    if legacy is False:
        return "continue"
    return "continue"


def _desired_runtime_command(slot: Dict[str, Any], runtime: Dict[str, Any]) -> List[str]:
    """Argv for vivi_pty: agent_launch wins over runtime.command when set."""
    launch = str(slot.get("agent_launch") or "").strip()
    if launch:
        try:
            return shlex.split(launch)
        except ValueError:
            return [launch]
    command = runtime.get("command")
    if isinstance(command, list) and command:
        return [str(part) for part in command]
    return []


def resolve_runtime_binding(
    fleet: Dict[str, Any],
    role: str,
    *,
    project: Optional[PathLike] = None,
    runtime_target: Optional[str] = None,
) -> Dict[str, Any]:
    """Derive one backend-neutral runtime binding from logical fleet + role."""
    name, slot, group = resolve_role(fleet, role)
    project_path = Path(project).expanduser().resolve() if project else None
    fleet_id = fleet_id_of(fleet, project_path)
    runtime = slot.get("runtime") if isinstance(slot.get("runtime"), dict) else {}
    kind = str(runtime.get("kind") or "tmux")
    mail_identity = str(slot.get("mail_identity") or name)
    cwd = str(slot.get("cwd") or (project_path if project_path else fleet.get("project") or ""))
    if isinstance(slot.get("packet"), dict):
        packet = slot["packet"]
        cwd = str(packet.get("worker_cwd") or packet.get("root") or cwd)
    assignment_mode = resolve_assignment_mode(slot if isinstance(slot, dict) else {})

    if kind == "vivi_pty":
        session_id = str(runtime.get("session_id") or mail_identity or name)
        socket = str(
            runtime.get("socket")
            or ((project_path / ".vivi" / "vivi-pty.sock") if project_path else "")
        )
        return {
            "fleet_id": fleet_id,
            "role": name,
            "group": group,
            "kind": kind,
            "mail_identity": mail_identity,
            "cwd": cwd,
            "target": runtime_target or session_id,
            "session": session_id,
            "window": "",
            "pane": "",
            "socket": socket,
            "agent": str(slot.get("agent") or "unknown"),
            "driver": str(runtime.get("driver") or slot.get("agent") or "generic"),
            "model": str(slot.get("agent_model") or ""),
            "launch": str(slot.get("agent_launch") or ""),
            # Prefer agent_launch argv (pi-hand/pi-head wrappers). Stale
            # runtime.command arrays historically re-bound Heads to plain pi.
            "runtime_command": _desired_runtime_command(slot, runtime),
            "min_seconds_between_wakes": int(
                180 if slot.get("min_seconds_between_wakes") is None
                else slot.get("min_seconds_between_wakes")
            ),
            "assignment_mode": assignment_mode,
        }

    configured_target = slot.get("tmux_target")
    target = str(runtime_target or configured_target or "")
    layout = str(fleet.get("tmux_layout") or "legacy")
    session = str(slot.get("tmux_session") or (fleet_id if layout == "session_per_fleet" else name))
    window = str(slot.get("tmux_window") or (name if layout == "session_per_fleet" else "1"))
    pane = str(slot.get("tmux_pane") or "1")
    if target:
        parsed_session, parsed_window, parsed_pane = _tmux_parts(target)
        session = parsed_session or session
        window = parsed_window or window
        pane = parsed_pane or pane
    else:
        target = "%s:%s.%s" % (session, window, pane)
    return {
        "fleet_id": fleet_id,
        "role": name,
        "group": group,
        "kind": kind,
        "mail_identity": mail_identity,
        "cwd": cwd,
        "target": target,
        "session": session,
        "window": window,
        "pane": pane,
        "socket": "",
        "agent": str(slot.get("agent") or "unknown"),
        "driver": str(slot.get("agent") or "generic"),
        "model": str(slot.get("agent_model") or ""),
        "launch": str(slot.get("agent_launch") or ""),
        "runtime_command": [],
        "min_seconds_between_wakes": int(
            180 if slot.get("min_seconds_between_wakes") is None
            else slot.get("min_seconds_between_wakes")
        ),
        "assignment_mode": assignment_mode,
    }
