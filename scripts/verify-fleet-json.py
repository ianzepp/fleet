#!/usr/bin/env python3
"""Validate the shape and cross-references of a fleet.json config.

  verify-fleet-json.py --project <root>
  verify-fleet-json.py --fleet-file /path/to/fleet.json
  verify-fleet-json.py --project <root> --json
  verify-fleet-json.py --project <root> --strict        # warnings count as errors
  verify-fleet-json.py --project <root> --no-path-checks # skip on-disk path refs

Checks JSON parse, required-for-function keys, cross-reference meaning
(mail_identity unique within the mailspace; auditor Hands use fresh
assignments), executive_cadence / wake-field well-formedness, and that
referenced absolute paths (role_prompt, persona, tooling binaries) exist.

The schema is intentionally permissive ("Recommended keys — extend freely; skill
cares about meanings"). This validator does NOT reject unknown keys. It reports
errors (would break a skill script) and warnings (suspicious but allowed).

--project/-p may appear before or after the flags. Default fleet path is
PROJECT/.vivi/fleet.json.

Requires: Python 3.9+ (macOS / Linux). Exit: 0 ok (warnings allowed) ·
1 validation errors (or any warning under --strict) · 2 usage/env.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    add_fleet_scope_arguments,
    ensure_dict,
    ensure_list,
    fleet_id_of,
    require_python,
)

require_python()

HEAD_KEYS = ("head-ceo", "head-cto", "head-cxo")
AUDITOR_HAND_RE = re.compile(r"^auditor-[1-9][0-9]*$")
TMUX_TARGET_RE = re.compile(r"^[^:\s]+:[^:\s]+(?:\.\d+)?$")
ABS_PLACEHOLDER_RE = re.compile(r"[<>]")


class Report:
    def __init__(self) -> None:
        self.errors: List[Tuple[str, str]] = []
        self.warnings: List[Tuple[str, str]] = []
        self.counts: Dict[str, int] = {"hands": 0, "heads": 0, "steward": 0}

    def err(self, where: str, msg: str) -> None:
        self.errors.append((where, msg))

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append((where, msg))


def _is_abs_real_path(s: Any) -> bool:
    """True for an absolute, non-templated path string worth checking on disk."""
    if not isinstance(s, str) or not s.startswith("/"):
        return False
    return not ABS_PLACEHOLDER_RE.search(s)


def _check_path(report: Report, where: str, key: str, val: Any, path_checks: bool) -> None:
    if not path_checks or not _is_abs_real_path(val):
        return
    if not Path(val).exists():
        report.warn(where, "%s references missing path: %s" % (key, val))


def _is_remote(entry: Dict[str, Any]) -> bool:
    host = str(entry.get("host") or "local").lower()
    return host not in ("", "local") or bool(entry.get("ssh"))


def _check_tmux_target(report: Report, where: str, entry: Dict[str, Any], required: bool) -> None:
    runtime = entry.get("runtime") or {}
    wake_mode = entry.get("wake_mode")
    harness = entry.get("harness")
    # Sub-agent harness: no tmux or PTY required at all.
    if harness == "subagent":
        for tmux_key in ("tmux_target", "tmux_session", "tmux_window"):
            if tmux_key in entry:
                report.err(where, "subagent role must not define %s" % tmux_key)
        return
    if wake_mode == "vivi_pty":
        report.err(where, "wake_mode=vivi_pty is retired; set runtime.kind=vivi_pty")
    runtime_kind = runtime.get("kind") if isinstance(runtime, dict) else None
    if runtime_kind not in (None, "vivi_pty"):
        report.err(where, "unsupported runtime.kind: %r" % runtime_kind)
    if runtime_kind == "vivi_pty":
        # vivi_pty runtime: no tmux target required; validate runtime command.
        if not isinstance(runtime, dict):
            report.err(where, "runtime must be an object for vivi_pty")
            return
        command = runtime.get("command")
        launch = entry.get("agent_launch")
        has_launch = isinstance(launch, str) and launch.strip()
        if not isinstance(command, list) or not command:
            # agent_launch alone is enough for fleet-runtime (preferred); still
            # prefer a stored runtime.command for vivi-pty-reinit and older tools.
            if has_launch:
                report.warn(
                    where,
                    "vivi_pty runtime.command missing; fleet-runtime will use agent_launch — "
                    "sync runtime.command to agent_launch argv to avoid reinit drift",
                )
            else:
                report.err(where, "vivi_pty runtime requires a non-empty command array (or agent_launch)")
        elif not all(isinstance(c, str) for c in command):
            report.err(where, "vivi_pty runtime.command must be an array of strings")
        elif has_launch:
            try:
                launch_argv = shlex.split(launch.strip())
            except ValueError:
                launch_argv = None
            if launch_argv is not None and list(command) != launch_argv:
                report.err(
                    where,
                    "agent_launch and runtime.command disagree — "
                    "agent_launch is canonical; update runtime.command to match "
                    "(stale runtime.command used to rebind heads to plain pi)",
                )
        for tmux_key in ("tmux_target", "tmux_session", "tmux_window"):
            if tmux_key in entry:
                report.err(where, "vivi_pty role cannot also define %s" % tmux_key)
        return
    target = entry.get("tmux_target")
    sess = entry.get("tmux_session")
    win = entry.get("tmux_window")
    if target is not None:
        if not isinstance(target, str) or not TMUX_TARGET_RE.match(target):
            report.err(where, "tmux_target malformed (want '<session>:<window>[.<pane>]'): %r" % target)
        return
    # no explicit target — sensors derive from session; doorbell prefers a target
    if not sess:
        if required:
            report.err(where, "missing tmux_target and tmux_session (cannot resolve pane)")
        else:
            report.warn(where, "no tmux_target (sensors derive from tmux_session; doorbell prefers a target)")
    elif win and not isinstance(sess, str):
        report.err(where, "tmux_session must be a string")


ASSIGNMENT_MODES = frozenset({"new", "compact", "continue", "restart"})


def _check_assignment_mode(report: Report, where: str, entry: dict) -> None:
    """Validate assignment_mode (and legacy clean_slate_per_assignment)."""
    mode = entry.get("assignment_mode")
    if mode is not None:
        if not isinstance(mode, str) or mode.strip().lower() not in ASSIGNMENT_MODES:
            report.err(
                where,
                "assignment_mode must be one of %s, got %r"
                % (sorted(ASSIGNMENT_MODES), mode),
            )
    legacy = entry.get("clean_slate_per_assignment")
    if legacy is not None and not isinstance(legacy, bool):
        report.err(
            where,
            "clean_slate_per_assignment must be boolean (legacy; prefer assignment_mode), got %r"
            % (legacy,),
        )
    if mode is not None and legacy is not None:
        report.warn(
            where,
            "both assignment_mode and clean_slate_per_assignment set; assignment_mode wins",
        )


def _check_inbox_key(report: Report, where: str, val: Any) -> None:
    if val is None:
        return
    if not isinstance(val, str) or not val.strip():
        report.err(where, "inbox key must be a non-empty string, got %r" % (val,))


def _register_mail_identity(
    report: Report,
    identities: Dict[str, str],
    where: str,
    mid: Any,
) -> None:
    """Require non-empty mail_identity; warn on duplicates across roles."""
    if not isinstance(mid, str) or not mid.strip():
        report.err(where, "missing mail_identity")
        return
    if mid in identities:
        report.warn(where, "duplicate mail_identity %r (also at %s)" % (mid, identities[mid]))
    else:
        identities[mid] = where


def _check_executive_cadence(report: Report, where: str, block: Dict[str, Any]) -> None:
    """Validate Head schedule dial: every_n_loops (0 = on-call, N>=1 = scheduled)."""
    if "self_directed" in block:
        report.warn(
            where + ".self_directed",
            "ignored/removed: Head schedule is only executive_cadence.every_n_loops "
            "(0=on-call, N>=1=scheduled); wake charter comes from persona+posture",
        )
    cad = block.get("executive_cadence")
    if cad is None:
        return
    cwhere = "%s.executive_cadence" % where
    if not isinstance(cad, dict):
        report.err(cwhere, "must be an object")
        return
    # Canonical dial: every_n_loops (0 = on-call; N >= 1 = scheduled)
    enl = cad.get("every_n_loops")
    if enl is not None:
        if not isinstance(enl, int) or isinstance(enl, bool) or enl < 0:
            report.err(
                "%s.every_n_loops" % cwhere,
                "must be an integer >= 0 (0=on-call, N>=1=scheduled), got %r" % (enl,),
            )
    en = cad.get("enabled")
    if en is not None:
        if not isinstance(en, bool):
            report.err("%s.enabled" % cwhere, "must be boolean if present (legacy), got %r" % (en,))
        else:
            report.warn(
                "%s.enabled" % cwhere,
                "legacy: prefer every_n_loops only (0=on-call; omit enabled). "
                "enabled:false ≡ every_n_loops:0; enabled:true without every_n_loops "
                "uses posture×role default",
            )
    # interval_sec / min_seconds_between_sweeps are legacy/ignored — warn if present.
    for legacy_key in ("interval_sec", "min_seconds_between_sweeps"):
        if legacy_key in cad:
            report.warn(
                "%s.%s" % (cwhere, legacy_key),
                "ignored: Head spacing is every_n_loops × mind_loop.interval_sec "
                "(set every_n_loops; see fleet-posture.md)",
            )
    if "sweep_mode" in cad and not isinstance(cad.get("sweep_mode"), str):
        report.warn("%s.sweep_mode" % cwhere, "should be a string, got %r" % (cad.get("sweep_mode"),))


def _check_sensor_log(report: Report, value: Any) -> None:
    if value is None:
        return
    where = "$.sensor_log"
    if not isinstance(value, dict):
        report.err(where, "must be an object")
        return
    if "enabled" in value and not isinstance(value.get("enabled"), bool):
        report.err(where + ".enabled", "must be boolean")
    level = value.get("level", "off")
    if level not in ("off", "events", "summary", "full"):
        report.err(where + ".level", "must be one of off, events, summary, full")
    if value.get("enabled") is True and level == "off":
        report.warn(where, "enabled=true with level=off records nothing")
    for key in ("path", "directory"):
        if key in value and (not isinstance(value[key], str) or not value[key].strip()):
            report.err(where + "." + key, "must be a non-empty path string")
    if "path" in value and "directory" in value:
        report.err(where, "set only one of path or directory")
    retention = value.get("retention_cycles")
    if retention is not None and (not isinstance(retention, int) or isinstance(retention, bool) or retention < 1):
        report.err(where + ".retention_cycles", "must be a positive integer")


def _check_lane_lifecycle(report: Report, value: Any) -> None:
    if value is None:
        return
    where = "$.lane_lifecycle"
    if not isinstance(value, dict):
        report.err(where, "must be an object")
        return
    for key, minimum in (
        ("stale_after_cycles", 1),
        ("resume_stale_after_hours", 0),
        ("release_grace_cycles", 0),
    ):
        raw = value.get(key)
        if raw is not None and (
            not isinstance(raw, int) or isinstance(raw, bool) or raw < minimum
        ):
            report.err("%s.%s" % (where, key), "must be an integer >= %d" % minimum)
    cleanup = value.get("worktree_cleanup", "manual")
    if cleanup != "manual":
        report.err(where + ".worktree_cleanup", "must be 'manual'; lane release never deletes worktrees")


def validate(fleet: Dict[str, Any], fleet_path: Path, path_checks: bool) -> Report:
    report = Report()
    if not isinstance(fleet, dict):
        report.err("$", "fleet.json top-level must be a JSON object")
        return report

    # --- top-level inboxes / scalars ---
    for k in ("mind_inbox", "operator_inbox", "head_report_inbox"):
        _check_inbox_key(report, "$.%s" % k, fleet.get(k))
    if "version" in fleet and not isinstance(fleet.get("version"), int):
        report.warn("$.version", "version should be an integer, got %r" % (fleet.get("version"),))
    _check_sensor_log(report, fleet.get("sensor_log"))
    _check_lane_lifecycle(report, fleet.get("lane_lifecycle"))

    # --- hands (may be keyed as 'hunters' in legacy fleets) ---
    hands = ensure_dict(fleet.get("hands") or fleet.get("hunters"))

    # --- steward ---
    st = fleet.get("steward")
    if st is not None:
        if not isinstance(st, dict):
            report.err("$.steward", "must be an object")
        else:
            report.counts["steward"] = 1
            if "enabled" in st and not isinstance(st.get("enabled"), bool):
                report.err("$.steward.enabled", "must be boolean, got %r" % (st.get("enabled"),))
            if st.get("enabled") is True:
                _check_tmux_target(report, "$.steward", st, required=True)

    # --- hands ---
    identities: Dict[str, str] = {}  # mail_identity -> where (for uniqueness)
    for name, h in hands.items():
        where = "hands.%s" % name
        if not isinstance(h, dict):
            report.err(where, "hand entry must be an object")
            continue
        report.counts["hands"] += 1
        _register_mail_identity(report, identities, where, h.get("mail_identity"))
        _check_tmux_target(report, where, h, required=True)
        if "agent" in h and not isinstance(h.get("agent"), str):
            report.warn(where, "agent must be a string, got %r" % (h.get("agent"),))
        cwd = h.get("cwd")
        if cwd is not None and isinstance(cwd, str) and cwd.startswith("/") and not _is_remote(h):
            if path_checks and not Path(cwd).is_dir():
                report.warn(where, "cwd does not exist locally: %s" % cwd)
        if name.startswith("auditor-") and not AUDITOR_HAND_RE.match(name):
            report.err(where, "auditor Hand name must match auditor-N with N >= 1")
        if AUDITOR_HAND_RE.match(name):
            if h.get("mail_identity") != name:
                report.err(where, "auditor mail_identity must match role name %r" % name)
            if h.get("assignment_mode") != "new":
                report.err(where, "auditor Hand requires assignment_mode='new' for independent review")
        pkt = h.get("packet")
        if pkt is not None and not isinstance(pkt, dict):
            report.warn(where, "packet must be an object or null (unassigned)")
        lane = h.get("lane")
        if lane is not None and not isinstance(lane, dict):
            report.err(where + ".lane", "must be an object or null")
        elif isinstance(lane, dict):
            lane_state = str(lane.get("state") or "").lower()
            wake_trigger = lane.get("wake_trigger") or lane.get("wake_triggers")
            if lane_state in ("parked", "deferred", "blocked", "hold") and not wake_trigger:
                report.warn(
                    where + ".lane",
                    "parked/deferred/blocked lane needs a wake trigger or remains a reconciliation candidate",
                )
        _check_assignment_mode(report, where, h)
        _check_path(report, where, "role_prompt", h.get("role_prompt"), path_checks)
        _check_path(report, where, "persona", h.get("persona"), path_checks)

    # --- heads ---
    for key in HEAD_KEYS:
        block = fleet.get(key)
        if block is None:
            continue
        where = "$.%s" % key
        if not isinstance(block, dict):
            report.err(where, "head entry must be an object")
            continue
        report.counts["heads"] += 1
        _register_mail_identity(report, identities, where, block.get("mail_identity"))
        if "agent" in block and not isinstance(block.get("agent"), str):
            report.warn(where, "agent must be a string, got %r" % (block.get("agent"),))
        la = block.get("legacy_aliases")
        if la is not None and not isinstance(la, list):
            report.warn(where, "legacy_aliases should be a list, got %r" % (type(la).__name__,))
        _check_assignment_mode(report, where, block)
        _check_executive_cadence(report, where, block)
        _check_path(report, where, "role_prompt", block.get("role_prompt"), path_checks)
        _check_path(report, where, "persona", block.get("persona"), path_checks)

    # --- tooling binaries ---
    tooling = fleet.get("tooling")
    if isinstance(tooling, dict):
        for tname, tblock in tooling.items():
            if not isinstance(tblock, dict):
                continue
            b = tblock.get("binary")
            if _is_abs_real_path(b) and path_checks and not Path(b).is_file():
                report.warn("$.tooling.%s.binary" % tname, "references missing binary: %s" % b)

    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate fleet.json shape, cross-references, and path refs (Python 3.9+)."
    )
    add_fleet_scope_arguments(ap, required_project=False)
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON output instead of text")
    ap.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    ap.add_argument("--no-path-checks", action="store_true", help="Skip on-disk existence checks for referenced paths")
    args = ap.parse_args(argv)

    fleet_path: Optional[Path] = None
    if args.fleet_file:
        fleet_path = Path(args.fleet_file).expanduser().resolve()
    elif args.project:
        fleet_path = Path(args.project).expanduser().resolve() / ".vivi" / "fleet.json"
    if not fleet_path:
        ap.error("provide --project or --fleet-file")
        return 2
    if not fleet_path.is_file():
        msg = "fleet.json not found: %s" % fleet_path
        if args.json:
            print(json.dumps({"ok": False, "fleet_path": str(fleet_path), "errors": [{"where": "$", "msg": msg}], "warnings": []}))
        else:
            print("INVALID: %s" % msg)
        return 1

    raw = fleet_path.read_text(encoding="utf-8")
    try:
        fleet = json.loads(raw)
    except json.JSONDecodeError as e:
        msg = "invalid JSON: %s (line %d col %d)" % (e.msg, e.lineno, e.colno)
        if args.json:
            print(json.dumps({"ok": False, "fleet_path": str(fleet_path), "errors": [{"where": "$", "msg": msg}], "warnings": []}))
        else:
            print("INVALID: %s" % msg)
        return 1

    report = validate(fleet, fleet_path, path_checks=not args.no_path_checks)
    fleet_id = fleet_id_of(fleet, fleet_path.parent.parent)
    if args.fleet and args.fleet != fleet_id:
        msg = "fleet ID mismatch: requested %r, configured %r" % (args.fleet, fleet_id)
        if args.json:
            print(json.dumps({"ok": False, "fleet_path": str(fleet_path), "errors": [{"where": "$", "msg": msg}], "warnings": []}))
        else:
            print("INVALID: %s" % msg)
        return 1

    hard = report.errors
    soft = report.warnings
    fail = bool(hard) or (args.strict and soft)

    if args.json:
        print(json.dumps({
            "ok": not fail,
            "fleet_id": fleet_id,
            "fleet_path": str(fleet_path),
            "errors": [{"where": w, "msg": m} for w, m in hard],
            "warnings": [{"where": w, "msg": m} for w, m in soft],
            "checked": report.counts,
            "strict": args.strict,
        }, indent=2, ensure_ascii=False))
    else:
        status = "INVALID" if fail else "OK"
        print("fleet %s: %s (%d errors, %d warnings)" % (fleet_id, status, len(hard), len(soft)))
        for where, msg in hard:
            print("  ERROR   %s: %s" % (where, msg))
        for where, msg in soft:
            print("  warn    %s: %s" % (where, msg))

    return 1 if fail else 0


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
