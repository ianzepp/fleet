#!/usr/bin/env python3
"""Validate and atomically rebind runtime configuration for fleet roles.

One validated role-rebind operation owns structured config mutation, safe
runtime lifecycle, readiness verification, and rollback. The helper supports
plan (dry-run) and apply subcommands.

  # Plan: show what would change without mutating
  fleet-runtime-rebind.py plan --project <root> \\
      --hands hand-1,hand-2 --model grok-4.5
  fleet-runtime-rebind.py plan --project <root> \\
      --heads all --agent pi --provider zai --model glm-5.2 --thinking high

  # Apply: atomically replace fleet.json + optionally restart panes
  fleet-runtime-rebind.py apply --project <root> \\
      --hands all --model grok-4.5
  fleet-runtime-rebind.py apply --project <root> \\
      --role hand-1 --role hand-2 --agent grok --model grok-4.5 \\
      --force-running

Selectors: --heads all, --hands all or comma names, repeatable --role.
Model fields: --agent, --provider, --model, plus --thinking or --reasoning.
Preserves identity, assignment, backend, and topology.
Generates canonical agent_launch for pi, grok, codex, opencode, kimi.
Updates runtime.command for vivi_pty roles.
Default: refuses active/running roles unless --force-running.
Backend-aware stop/start/readiness for tmux and vivi_pty.
Rollback config/processes on partial failure.

Requires: Python 3.9+ (macOS / Linux). Exit: 0 ok · 1 error · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    FleetScopeError,
    ensure_dict,
    exact_tmux_session,
    exact_tmux_target,
    load_json,
    now_iso as _now_iso,
    require_python,
    resolve_fleet_file,
    resolve_runtime_binding,
    run_cmd,
    save_json,
)

require_python()

HARNESS_LAUNCHERS = ("grok", "codex", "pi", "opencode", "kimi")
VIVI_PTY_DRIVERS = frozenset(("generic", "grok", "codex", "pi", "opencode", "kimi"))
CANONICAL_STATES_FOR_RESTART = (
    "waiting_for_input",
    "completed",
    "stopped",
    "failed",
    "unknown",
)
RUNNING_STATES = frozenset({"starting", "submitting", "running", "approval_required"})

# Runtime binding blocks keyed by top-level fleet.json identity (head-ceo, hand-1, …).
HEAD_IDENTITIES = frozenset({
    "head-ceo", "head-cto", "head-cxo", "head-cpo",
    "head-coo", "head-cso", "head-cfo", "head-cmo",
})


def now_iso() -> str:
    return _now_iso()


def _pi_wrapper_path(role_group: str) -> str:
    """Absolute path to fleet skill pi-hand / pi-head (falls back to bare name)."""
    scripts = Path(__file__).resolve().parent
    name = "pi-head" if role_group == "head" else "pi-hand"
    candidate = scripts / name
    return str(candidate) if candidate.is_file() else name


def _build_pi_argv(
    role_group: str,
    agent_model: Optional[str],
    provider: Optional[str],
    effort: Optional[str],
    approve: bool,
    *,
    name: Optional[str] = None,
) -> List[str]:
    """Pi argv via role wrapper so Fleet Mind extension never loads in workers."""
    args: List[str] = [_pi_wrapper_path(role_group)]
    if provider:
        args += ["--provider", provider]
    if agent_model:
        args += ["--model", agent_model]
    if effort:
        args += ["--thinking", effort]
    if name:
        args += ["--name", name]
    if approve:
        args.append("--approve")
    return args


def _build_launch(agent: str, agent_model: Optional[str], provider: Optional[str],
                  thinking: Optional[str], reasoning: Optional[str],
                  approve: bool = True, role_group: str = "hand",
                  launch_name: Optional[str] = None) -> Optional[str]:
    """Build a canonical agent_launch argv string for the given harness.

    Returns a single-quoted shell command string, or None if the harness is
    unknown.  Uses shlex.quote on each component to avoid eval-style flattening.
    Pi Hands/Heads use fleet skill wrappers (pi-hand / pi-head).
    """
    effort = thinking or reasoning
    agent_lower = agent.lower() if agent else ""
    model = agent_model or ""

    if agent_lower == "grok":
        args: List[str] = ["grok"]
        if model:
            args += ["--model", model]
        if approve:
            args.append("--always-approve")
        return " ".join(shlex.quote(a) for a in args)

    if agent_lower == "codex":
        args = ["codex"]
        if model:
            args += ["--model", model]
        if effort:
            args += ["-c", "model_reasoning_effort=%s" % effort]
        args += ["-s", "danger-full-access"]
        return " ".join(shlex.quote(a) for a in args)

    if agent_lower == "pi":
        args = _build_pi_argv(role_group, model, provider, effort, approve, name=launch_name)
        return " ".join(shlex.quote(a) for a in args)

    if agent_lower == "opencode":
        args = ["opencode"]
        if model:
            args += ["--model", model]
        if effort:
            args += ["--variant", effort]
        if approve:
            args.append("--auto")
        return " ".join(shlex.quote(a) for a in args)

    if agent_lower == "kimi":
        args = ["kimi"]
        if model:
            args += ["--model", model]
        if approve:
            args.append("--yolo")
        return " ".join(shlex.quote(a) for a in args)

    return None  # unknown harness — caller uses existing agent_launch


def _update_runtime_command(runtime: dict, agent: str, agent_model: Optional[str],
                             provider: Optional[str], thinking: Optional[str],
                             reasoning: Optional[str],
                             role_group: str = "hand",
                             launch_name: Optional[str] = None) -> dict:
    """For vivi_pty roles, produce a new runtime.command list (must match agent_launch)."""
    effort = thinking or reasoning
    agent_lower = agent.lower() if agent else ""
    model = agent_model or ""

    if agent_lower == "grok":
        cmd: List[str] = ["grok"]
        if model:
            cmd += ["--model", model]
        cmd.append("--always-approve")
    elif agent_lower == "codex":
        cmd = ["codex"]
        if model:
            cmd += ["--model", model]
        if effort:
            cmd += ["-c", "model_reasoning_effort=%s" % effort]
        cmd += ["-s", "danger-full-access"]
    elif agent_lower == "pi":
        cmd = _build_pi_argv(role_group, model, provider, effort, True, name=launch_name)
    elif agent_lower == "opencode":
        cmd = ["opencode"]
        if model:
            cmd += ["--model", model]
        if effort:
            cmd += ["--variant", effort]
        cmd.append("--auto")
    elif agent_lower == "kimi":
        cmd = ["kimi"]
        if model:
            cmd += ["--model", model]
        cmd.append("--yolo")
    else:
        return runtime  # preserve existing

    updated = dict(runtime)
    updated["command"] = cmd
    if agent_lower in VIVI_PTY_DRIVERS:
        updated["driver"] = agent_lower
    return updated


def _resolve_slots(fleet: dict, head_selector: Optional[str],
                   hand_selector: Optional[str],
                   roles: Optional[List[str]]) -> Set[str]:
    """Resolve named selectors into a set of top-level identity keys."""
    selected: Set[str] = set()

    if head_selector is not None:
        if head_selector == "all":
            selected.update(k for k in fleet if k.startswith("head-") and isinstance(fleet.get(k), dict))
        else:
            selected.update(name.strip() for name in head_selector.split(",") if name.strip())

    if hand_selector is not None:
        hands_block = fleet.get("hands") if isinstance(fleet.get("hands"), dict) else {}
        if hand_selector == "all":
            selected.update(k for k in hands_block if isinstance(hands_block.get(k), dict))
        else:
            selected.update(name.strip() for name in hand_selector.split(",") if name.strip())

    if roles:
        selected.update(r.strip() for r in roles if r.strip())

    return selected


def _binding_for_slot(project: Path, identity: str, slot: dict, fleet: Optional[dict] = None) -> dict:
    source = fleet if isinstance(fleet, dict) else {"hands": {identity: slot}}
    return resolve_runtime_binding(source, identity, project=project)


def _load_runtime_state(project: Path, identity: str, slot: dict, fleet: Optional[dict] = None) -> Optional[dict]:
    """Snapshot runtime state for one role before mutation.

    Returns None if the role has no known runtime backend.
    """
    runtime = slot.get("runtime") if isinstance(slot.get("runtime"), dict) else {}
    kind = runtime.get("kind") or "tmux"
    if kind == "vivi_pty":
        return _snapshot_vivi_pty(project, identity, slot)
    return _snapshot_tmux(project, identity, slot, fleet)


def _snapshot_tmux(project: Path, identity: str, slot: dict, fleet: Optional[dict] = None) -> Optional[dict]:
    target = _binding_for_slot(project, identity, slot, fleet)["target"]
    session = target.split(":")[0]
    tmux = shutil.which("tmux") or "tmux"
    rc, _ = run_cmd([tmux, "has-session", "-t", exact_tmux_session(session)], timeout=5)
    if rc != 0:
        return {"kind": "tmux", "target": target, "state": "stopped", "session": session}
    rc2, text = run_cmd(
        [tmux, "capture-pane", "-t", exact_tmux_target(target), "-p", "-S", "-20"],
        timeout=5,
    )
    tail = text if rc2 == 0 else ""
    state = _classify_tail(tail)
    return {"kind": "tmux", "target": target, "state": state, "session": session, "tail": tail}


def _snapshot_vivi_pty(project: Path, identity: str, slot: dict) -> Optional[dict]:
    runtime = slot.get("runtime") if isinstance(slot.get("runtime"), dict) else {}
    session_id = runtime.get("session_id") or slot.get("mail_identity") or identity
    socket = runtime.get("socket") or str(project / ".vivi" / "vivi-pty.sock")
    vivi_pty = shutil.which("vivi-pty") or "vivi-pty"
    rc, out = run_cmd(
        [vivi_pty, "session", "diagnostic", session_id, "--socket", socket],
        timeout=5,
    )
    if rc != 0:
        return {"kind": "vivi_pty", "target": session_id, "socket": socket, "state": "stopped"}
    try:
        diag = json.loads(out)
    except Exception:
        return {"kind": "vivi_pty", "target": session_id, "socket": socket, "state": "unknown"}
    process = diag.get("process_state") or (diag.get("session") or {}).get("state", "unknown")
    if process in ("exited", "stopped"):
        state = "stopped"
    else:
        state = diag.get("harness_state", "unknown")
    return {
        "kind": "vivi_pty",
        "target": session_id,
        "socket": socket,
        "state": state,
        "process_state": process,
    }


def _classify_tail(text: str) -> str:
    t = text or ""
    last_lines = [line for line in t.splitlines() if line.strip()]
    bottom = "\n".join(last_lines[-6:]) if last_lines else ""
    if re.search(
        r"Working \(|esc to interrupt|Waiting for response|Responding|Thinking…"
        r"|[🌑🌒🌓🌔🌕🌖🌗🌘]\s*·\s*Tip:",
        t,
        re.I,
    ):
        return "running"
    if re.search(
        r"Yes, continue|Do you trust|trust this workspace|Always allow|Allow once"
        r"|Approve once|Approve for this session|Reject with feedback|Write this file\?|↵ confirm",
        t,
        re.I,
    ):
        return "approval_required"
    if re.search(r"over capacity|rate limit|[^0-9]429[^0-9]|usage limit hard|try again later", t, re.I):
        return "failed"
    if re.search(r"ECONNRESET|connection failed|connection error|connect timed out", t, re.I):
        return "failed"
    if "›" in t:
        if re.search(r"bag empty|standing by|turn end|Turn completed|ready-to-merge", t, re.I):
            return "completed"
        return "waiting_for_input"
    if re.search(r"❯\s*$|╰─.*Grok|codex ›|^\s*›\s*$", t, re.M):
        return "waiting_for_input"
    if "OpenCode Zen" in t or "Build ·" in t:
        return "waiting_for_input"
    if last_lines and re.search(r"context:\s*\d+%", last_lines[-1]):
        if re.search(r"│\s*>\s*", bottom):
            return "waiting_for_input"
    return "unknown"


def _stop_tmux(target: str, session: str) -> Tuple[bool, str]:
    """Stop a tmux pane. Returns (ok, message)."""
    tmux = shutil.which("tmux") or "tmux"
    target_t = exact_tmux_target(target)
    rc, _ = run_cmd([tmux, "has-session", "-t", exact_tmux_session(session)], timeout=5)
    if rc != 0:
        return True, "already stopped"
    rc2, out = run_cmd([tmux, "send-keys", "-t", target_t, "C-c"], timeout=5)
    time.sleep(0.3)
    rc3, _ = run_cmd([tmux, "send-keys", "-t", target_t, "C-c"], timeout=5)
    time.sleep(0.2)
    return rc2 == 0 or rc3 == 0, out if rc2 != 0 else ""


def _stop_vivi_pty(session_id: str, socket: str) -> Tuple[bool, str]:
    """Remove a vivi_pty session so the same id can bind new config."""
    vivi_pty = shutil.which("vivi-pty") or "vivi-pty"
    rc, out = run_cmd(
        [vivi_pty, "session", "remove", session_id, "--socket", socket],
        timeout=10,
    )
    return rc == 0, out


def _start_tmux(slot: dict, identity: str, cwd: Optional[str],
                restart: bool = False, fleet: Optional[dict] = None,
                project: Optional[Path] = None) -> Tuple[bool, str]:
    """Start a tmux session for a role. Returns (ok, message).

    When restart=True and the session already exists, launch the new process
    inside the existing pane via send-keys so the window/topology is preserved.
    """
    target = _binding_for_slot(project or Path(cwd or "."), identity, slot, fleet)["target"]
    session = target.split(":")[0]
    launch = (slot.get("agent_launch") or "").strip()
    tmux = shutil.which("tmux") or "tmux"
    target_t = exact_tmux_target(target)
    rc, _ = run_cmd([tmux, "has-session", "-t", exact_tmux_session(session)], timeout=5)
    if rc == 0:
        if restart and launch:
            work_dir = cwd or "."
            try:
                parts = shlex.split(launch)
            except ValueError:
                parts = [launch]
            full_cmd = " ".join(shlex.quote(p) for p in parts)
            rc2, out = run_cmd(
                [tmux, "send-keys", "-t", target_t, full_cmd, "Enter"],
                timeout=10,
            )
            return rc2 == 0, out
        return True, "session exists"
    if not launch:
        return False, "no agent_launch to start"
    work_dir = cwd or "."
    try:
        parts = shlex.split(launch)
    except ValueError:
        parts = [launch]
    full_cmd = " ".join(shlex.quote(p) for p in parts)
    # -s takes the literal session name (no = exact-match prefix).
    rc2, out = run_cmd(
        [tmux, "new-session", "-d", "-s", session, "-c", work_dir, full_cmd],
        timeout=10,
    )
    return rc2 == 0, out


def _start_vivi_pty(slot: dict, identity: str, cwd: Optional[str],
                     project: Path) -> Tuple[bool, str]:
    """Start a vivi_pty session for a role. Returns (ok, message)."""
    runtime = slot.get("runtime") if isinstance(slot.get("runtime"), dict) else {}
    session_id = runtime.get("session_id") or slot.get("mail_identity") or identity
    socket = runtime.get("socket") or str(project / ".vivi" / "vivi-pty.sock")
    command = runtime.get("command")
    if not isinstance(command, list) or not command:
        return False, "no runtime.command to start"
    vivi_pty = shutil.which("vivi-pty") or "vivi-pty"
    work_dir = cwd or str(project)
    driver = str(runtime.get("driver") or "generic")
    args = [
        vivi_pty,
        "session",
        "start",
        session_id,
        "--socket",
        socket,
        "--cwd",
        work_dir,
        "--driver",
        driver,
        "--",
    ]
    args.extend(command)
    rc, out = run_cmd(args, timeout=15)
    return rc == 0, out


def _check_readiness(slot: dict, identity: str, project: Path,
                     timeout_sec: float = 10.0, fleet: Optional[dict] = None) -> Tuple[bool, str]:
    """Poll until the runtime is ready (running/waiting_for_input/completed) or timeout."""
    runtime = slot.get("runtime") if isinstance(slot.get("runtime"), dict) else {}
    kind = runtime.get("kind") or "tmux"
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        state = _load_runtime_state(project, identity, slot, fleet)
        if state is None:
            return False, "unable to read runtime state"
        current = state.get("state", "unknown")
        if current not in ("stopped", "unknown", "failed"):
            return True, current
        time.sleep(0.5)
    return False, "timeout waiting for readiness"


def _validate_candidate(candidate: Path, script_dir: Path) -> None:
    """Run verify-fleet-json.py --strict on the candidate fleet.json.

    Errors raise ValueError; missing verifier script emits a warning but continues.
    """
    verifier = script_dir / "verify-fleet-json.py"
    if not verifier.is_file():
        sys.stderr.write("warning: verify-fleet-json.py not found, skipping strict validation\n")
        return
    result = subprocess.run(
        [sys.executable, str(verifier), "--fleet-file", str(candidate), "--strict"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("candidate failed strict validation:\n%s" % result.stdout.rstrip())


def _atomic_replace(path: Path, fleet: dict, script_dir: Path) -> None:
    """Write fleet.json atomically with strict validation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".%s." % path.name,
        suffix=".tmp",
        dir=str(path.parent),
    )
    candidate = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(fleet, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        _validate_candidate(candidate, script_dir)
        os.replace(str(candidate), str(path))
    finally:
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def _build_change_plan(
    fleet: dict,
    selected: Set[str],
    agent: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    thinking: Optional[str],
    reasoning: Optional[str],
    force_running: bool,
    sync_mind: bool,
    allow_hand_exception: bool,
    hand_exception_note: str,
    project: Path,
) -> Tuple[List[dict], List[str]]:
    """Build a change plan: list of (before/after) dicts and warnings."""
    changes: List[dict] = []
    warnings: List[str] = []
    hands_block = fleet.get("hands") if isinstance(fleet.get("hands"), dict) else {}
    mind_agent = (fleet.get("mind") or {}).get("agent") if isinstance(fleet.get("mind"), dict) else None

    for identity in sorted(selected):
        entry = fleet.get(identity)
        if identity in hands_block:
            # This is a Hand identity found via hands block
            # We already selected them correctly; check if entry is in fleet root Heads section
            if isinstance(entry, dict) and identity not in HEAD_IDENTITIES:
                pass  # Hand selected from hands block
            else:
                # Need to get the actual entry from hands block
                pass
        if not isinstance(entry, dict):
            # Try hands block
            if identity in hands_block:
                entry = hands_block[identity]
            else:
                warnings.append("unknown identity: %s" % identity)
                continue

        before = dict(entry)
        after = dict(entry)
        runtime = dict(after.get("runtime") if isinstance(after.get("runtime"), dict) else {})
        runtime_kind = runtime.get("kind") or "tmux"

        # Capture current state
        current_state = _load_runtime_state(project, identity, entry, fleet)
        current_class = (current_state or {}).get("state", "unknown")

        # Check running guard
        if not force_running and current_class in RUNNING_STATES:
            warnings.append(
                "%s is %s (refusing; use --force-running to override)" % (identity, current_class)
            )
            continue

        is_head = identity in HEAD_IDENTITIES
        is_hand = identity in hands_block or identity.startswith("hand-")

        # If Hand harness is changing and not synced
        if is_hand:
            new_agent = agent or entry.get("agent")
            if new_agent and mind_agent and new_agent.lower() != str(mind_agent).lower() and not sync_mind:
                if not allow_hand_exception:
                    warnings.append(
                        "%s: Hand harness would diverge from Mind (%s → %s). "
                        "Use --allow-hand-exception or --sync-mind." % (
                            identity, mind_agent, new_agent
                        )
                    )
                    continue

        # Apply model changes
        if agent is not None:
            after["agent"] = agent
        if provider is not None:
            after["provider"] = provider
        if model is not None:
            after["agent_model"] = model
        if thinking is not None:
            after["thinking"] = thinking
        if reasoning is not None and thinking is None:
            after["agent_reasoning_effort"] = reasoning

        new_agent = agent or entry.get("agent", "")
        new_model = model or entry.get("agent_model")
        new_provider = provider or entry.get("provider")
        new_effort = thinking or reasoning

        role_group = "head" if is_head else "hand"
        # Preserve --name from existing launch when present (pane labels).
        launch_name = None
        existing_launch = str(entry.get("agent_launch") or "")
        if existing_launch:
            try:
                existing_argv = shlex.split(existing_launch)
            except ValueError:
                existing_argv = []
            for i, tok in enumerate(existing_argv):
                if tok == "--name" and i + 1 < len(existing_argv):
                    launch_name = existing_argv[i + 1]
                    break

        # Generate canonical launch (pi → pi-hand / pi-head wrappers)
        launch = _build_launch(
            new_agent, new_model, new_provider, thinking, reasoning,
            role_group=role_group, launch_name=launch_name,
        )
        if launch is not None:
            after["agent_launch"] = launch
        elif entry.get("agent_launch"):
            # If agent is changing but we can't generate a launch, warn
            pass  # keep existing launch

        # Update vivi_pty runtime.command — must match agent_launch
        if runtime_kind == "vivi_pty":
            updated_runtime = _update_runtime_command(
                runtime, new_agent, new_model, new_provider, thinking, reasoning,
                role_group=role_group, launch_name=launch_name,
            )
            after["runtime"] = updated_runtime

        # Clear stale provider/model/reasoning if switching agents
        if agent and is_head and agent.lower() == "pi":
            # Pi uses thinking, not reasoning
            if "agent_reasoning_effort" in after and "thinking" in after:
                del after["agent_reasoning_effort"]

        changes.append({
            "identity": identity,
            "is_head": is_head,
            "is_hand": is_hand,
            "before": before,
            "after": after,
            "current_state": current_class,
            "runtime_kind": runtime_kind,
        })

    return changes, warnings


def cmd_plan(args: argparse.Namespace, project: Path, fleet_path: Path) -> int:
    fleet = load_json(fleet_path)
    if not fleet:
        print("error: empty or invalid fleet.json", file=sys.stderr)
        return 1

    selected = _resolve_slots(fleet, args.heads, args.hands, args.role)
    if not selected:
        print("error: no roles selected (use --heads, --hands, --role)", file=sys.stderr)
        return 2

    changes, warnings = _build_change_plan(
        fleet, selected,
        args.agent, args.provider, args.model, args.thinking, args.reasoning,
        args.force_running, args.sync_mind, args.allow_hand_exception,
        args.allow_hand_exception_note or "", project,
    )

    print("PLAN: %d role(s) selected, %d change(s) prepared, %d warning(s)"
          % (len(selected), len(changes), len(warnings)))
    if warnings:
        for w in warnings:
            print("  WARNING: %s" % w)
    if not changes:
        print("  No changes to apply.")
        return 0

    for c in changes:
        print()
        print("  %s (%s, runtime=%s, state=%s)" % (
            c["identity"],
            "head" if c["is_head"] else "hand",
            c["runtime_kind"],
            c["current_state"],
        ))
        before = c["before"]
        after = c["after"]
        diffs: List[str] = []
        for key in ("agent", "provider", "agent_model", "thinking",
                     "agent_reasoning_effort", "agent_launch"):
            bv = before.get(key)
            av = after.get(key)
            if bv != av:
                diffs.append("  %s: %r → %r" % (key, bv, av))
        # Check runtime.command for vivi_pty
        before_rt = before.get("runtime") if isinstance(before.get("runtime"), dict) else {}
        after_rt = after.get("runtime") if isinstance(after.get("runtime"), dict) else {}
        before_cmd = before_rt.get("command")
        after_cmd = after_rt.get("command")
        if before_cmd != after_cmd:
            diffs.append("  runtime.command: %s → %s" % (
                json.dumps(before_cmd) if before_cmd else "(none)",
                json.dumps(after_cmd) if after_cmd else "(none)",
            ))
        if diffs:
            for d in diffs:
                print(d)
        else:
            print("  (no material changes)")

    return 0


def cmd_apply(args: argparse.Namespace, project: Path, fleet_path: Path) -> int:
    fleet = load_json(fleet_path)
    if not fleet:
        print("error: empty or invalid fleet.json", file=sys.stderr)
        return 1

    selected = _resolve_slots(fleet, args.heads, args.hands, args.role)
    if not selected:
        print("error: no roles selected (use --heads, --hands, --role)", file=sys.stderr)
        return 2

    changes, warnings = _build_change_plan(
        fleet, selected,
        args.agent, args.provider, args.model, args.thinking, args.reasoning,
        args.force_running, args.sync_mind, args.allow_hand_exception,
        args.allow_hand_exception_note or "", project,
    )

    if warnings:
        for w in warnings:
            print("WARNING: %s" % w, file=sys.stderr)
    if not changes:
        print("No changes to apply.")
        return 0

    # Build the updated fleet dict
    updated = dict(fleet)
    hands_block = dict(fleet.get("hands") if isinstance(fleet.get("hands"), dict) else {})
    for c in changes:
        identity = c["identity"]
        after = c["after"]
        if identity in HEAD_IDENTITIES:
            updated[identity] = after
        elif identity in hands_block:
            hands_block[identity] = after
        else:
            updated[identity] = after
    updated["hands"] = hands_block

    # Backup the original for rollback
    original = dict(fleet)
    original_hands = dict(fleet.get("hands") if isinstance(fleet.get("hands"), dict) else {})

    # Atomic write
    script_dir = Path(__file__).resolve().parent
    try:
        _atomic_replace(fleet_path, updated, script_dir)
        print("applied %d change(s) to %s" % (len(changes), fleet_path))
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    # Restart if requested
    if args.restart:
        print("restarting panes…")
        rollback_needed = False
        rollback_identities: List[str] = []
        for c in changes:
            identity = c["identity"]
            entry = c["after"]
            # Stop
            if c["runtime_kind"] == "vivi_pty":
                runtime = entry.get("runtime") if isinstance(entry.get("runtime"), dict) else {}
                sid = runtime.get("session_id") or entry.get("mail_identity") or identity
                sock = runtime.get("socket") or str(project / ".vivi" / "vivi-pty.sock")
                ok, msg = _stop_vivi_pty(sid, sock)
                if not ok:
                    print("  WARNING: failed to stop %s: %s" % (identity, msg), file=sys.stderr)
            else:
                target = resolve_runtime_binding(updated, identity, project=project)["target"]
                session = target.split(":")[0]
                ok, msg = _stop_tmux(target, session)
                if not ok:
                    print("  WARNING: failed to stop %s: %s" % (identity, msg), file=sys.stderr)
            print("  stopped %s" % identity)

            # Start (brief settle so tmux shell recovers after C-c)
            if c["runtime_kind"] != "vivi_pty":
                time.sleep(0.5)
            cwd_val = entry.get("cwd") or str(project)
            if c["runtime_kind"] == "vivi_pty":
                ok, msg = _start_vivi_pty(entry, identity, cwd_val, project)
            else:
                ok, msg = _start_tmux(entry, identity, cwd_val, restart=True, fleet=updated, project=project)
            if not ok:
                print("  ERROR: failed to start %s: %s" % (identity, msg), file=sys.stderr)
                rollback_needed = True
                rollback_identities.append(identity)
                continue
            print("  started %s" % identity)

            # Readiness check
            ready, state = _check_readiness(entry, identity, project, timeout_sec=30.0, fleet=updated)
            if ready:
                print("  %s ready (state=%s)" % (identity, state))
            else:
                print("  WARNING: %s may not be ready: %s" % (identity, state), file=sys.stderr)

        if rollback_needed:
            print("ROLLBACK: restoring original config for %s" % ", ".join(rollback_identities))
            rollback = dict(original)
            rb_hands = dict(original_hands)
            for rid in rollback_identities:
                if rid in HEAD_IDENTITIES:
                    rollback[rid] = original.get(rid, {})
                elif rid in rb_hands:
                    rb_hands[rid] = original_hands.get(rid, {})
                elif rid in original:
                    rollback[rid] = original.get(rid, {})
            rollback["hands"] = rb_hands
            try:
                _atomic_replace(fleet_path, rollback, script_dir)
                print("  rolled back fleet.json")
            except ValueError as exc:
                print("  CRITICAL: rollback failed: %s" % exc, file=sys.stderr)
            return 1

    return 0


def _extract_globals(argv: List[str]) -> Tuple[List[str], Optional[str], Optional[str], Optional[str]]:
    """Allow project, logical fleet, and fleet-file before/after the subcommand."""
    project = None  # type: Optional[str]
    fleet_id = None  # type: Optional[str]
    fleet_file = None  # type: Optional[str]
    out: List[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--project", "-p") and i + 1 < len(argv):
            project = argv[i + 1]
            i += 2
            continue
        if a.startswith("--project="):
            project = a.split("=", 1)[1]
            i += 1
            continue
        if a.startswith("-p=") and len(a) > 3:
            project = a[3:]
            i += 1
            continue
        if a in ("--fleet", "-f") and i + 1 < len(argv):
            fleet_id = argv[i + 1]
            i += 2
            continue
        if a.startswith("--fleet="):
            fleet_id = a.split("=", 1)[1]
            i += 1
            continue
        if a == "--fleet-file" and i + 1 < len(argv):
            fleet_file = argv[i + 1]
            i += 2
            continue
        if a.startswith("--fleet-file="):
            fleet_file = a.split("=", 1)[1]
            i += 1
            continue
        out.append(a)
        i += 1
    return out, project, fleet_id, fleet_file


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Validate and atomically rebind runtime configuration for fleet roles.",
    )
    sub = p.add_subparsers(dest="command")
    sub.required = True  # type: ignore[attr-defined]

    for cmd_name, cmd_help in (("plan", "Dry-run: show changes without mutating"),
                                ("apply", "Atomically apply runtime rebinds")):
        sp = sub.add_parser(cmd_name, help=cmd_help)
        sp.add_argument("--heads", default=None,
                        help='"all" or comma-separated head identities (head-ceo,head-cto,…)')
        sp.add_argument("--hands", default=None,
                        help='"all" or comma-separated hand identities (hand-1,hand-2,…)')
        sp.add_argument("--role", action="append", default=None,
                        help="repeatable: select individual roles by identity")
        sp.add_argument("--agent", default=None, help="agent harness (grok, codex, pi, opencode, kimi)")
        sp.add_argument("--provider", default=None, help="provider name (zai, openai-codex, etc.)")
        sp.add_argument("--model", default=None, help="model identifier")
        sp.add_argument("--thinking", default=None, help="thinking/reasoning effort level")
        sp.add_argument("--reasoning", default=None,
                        help="reasoning effort (alias for --thinking; prefer --thinking)")
        sp.add_argument("--force-running", action="store_true",
                        help="Force rebind even for active/running roles")
        sp.add_argument("--sync-mind", action="store_true",
                        help="Also rebind mind.agent to match Hand harness")
        sp.add_argument("--allow-hand-exception", action="store_true",
                        help="Allow Hand harness divergence from Mind")
        sp.add_argument("--allow-hand-exception-note", default=None,
                        help="One-line note recording why Hand harness diverges")
        # apply-only flags
        if cmd_name == "apply":
            sp.add_argument("--restart", action="store_true",
                            help="Stop, restart, and check readiness of affected panes")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    rest, project_arg, fleet_id_arg, fleet_file_arg = _extract_globals(raw)
    args = parser().parse_args(rest)
    project_s = project_arg
    if not project_s:
        print("error: --project/-p is required (before or after the subcommand)", file=sys.stderr)
        return 2
    project = Path(project_s).expanduser().resolve()
    if not project.is_dir():
        print("error: project is not a directory: %s" % project, file=sys.stderr)
        return 1
    try:
        fleet_path, _ = resolve_fleet_file(project, fleet_id_arg, fleet_file_arg)
    except FleetScopeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    if args.command == "plan":
        return cmd_plan(args, project, fleet_path)
    if args.command == "apply":
        return cmd_apply(args, project, fleet_path)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)
