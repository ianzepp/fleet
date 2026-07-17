#!/usr/bin/env python3
"""Read/update fleet mind-baseline.json for FLEET_CYCLE bookkeeping.

  fleet-baseline.py [--project <root>] get
  fleet-baseline.py get --project <root>
  fleet-baseline.py bump -p <root> --summary '…' [--acted|--quiet] \\
      [--mode interactive|autonomous] [--kind superficial|thorough|wind_down] \\
      [--fingerprint-file sensors.json] [--fingerprint-json '{…}'] \\
      [--runtime-states-json '{…}'] [--debt-json '[…]'] [--recap 'line'] \\
      [--operator-engaged] [--no-increment-silence] \\
      [--mind-session label] [--mind-host hostname] [--detach]
  fleet-baseline.py rearm-note -p <root>
  fleet-baseline.py wound-up -p <root> --summary '…' [--dropped hand-1,hand-2]

--project/-p may appear before or after the subcommand.
bump with full sensors JSON also merges sensors.heads → baseline head-*
last_report_handle / last_report_at (executive cadence + report absorb).

--mind-session sets the advisory mind_session lock on attach (also sets
  mind_loop.state=attached). --detach clears mind_session and sets state
  to detached. Always use --mind-session or --detach instead of hand-editing
  the baseline JSON.

Requires: Python 3.9+ (macOS / Linux). Exit: 0 ok · 1 error · 2 usage/env
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    FleetScopeError,
    add_fleet_scope_arguments,
    ensure_dict,
    ensure_list,
    load_json,
    now_iso,
    require_python,
    resolve_fleet_file,
    save_json,
)

require_python()

# Fingerprint keys that used to smuggle durable head report state (retired).
_LEGACY_HEAD_FP_PREFIX = "head_"
_LEGACY_HEAD_FP_SUFFIXES = ("_last_handle", "_last_completed")


def load_baseline(path: Path) -> dict:
    if not path.is_file():
        return {"version": 1, "project": str(path.parent.parent)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print("error reading baseline: %s" % exc, file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict):
        print("error reading baseline: root must be a JSON object", file=sys.stderr)
        sys.exit(1)
    return data


def ensure_ml(b: dict) -> dict:
    ml = b.get("mind_loop")
    if not isinstance(ml, dict):
        ml = {}
        b["mind_loop"] = ml
    return ml


def apply_head_report_state(b: dict, heads: Any) -> None:
    """Write sensors.heads sweep_* into baseline head-* last_report_* keys."""
    if not isinstance(heads, dict):
        return
    for hkey, hdata in heads.items():
        if not isinstance(hkey, str) or not hkey.startswith("head-"):
            continue
        if not isinstance(hdata, dict):
            continue
        handle = hdata.get("sweep_last_handle")
        completed = hdata.get("sweep_last_completed")
        if handle is None and completed is None:
            continue
        hb = ensure_dict(b.get(hkey))
        if handle is not None:
            hb["last_report_handle"] = handle
        if completed is not None:
            hb["last_report_at"] = completed
        b[hkey] = hb


def strip_legacy_head_fp_keys(fp: dict) -> None:
    """Drop retired head_*_last_* keys from a fingerprint dict (in place)."""
    for key in list(fp.keys()):
        if not isinstance(key, str) or not key.startswith(_LEGACY_HEAD_FP_PREFIX):
            continue
        if key.endswith(_LEGACY_HEAD_FP_SUFFIXES):
            del fp[key]


def _parse_json_arg(raw: str, label: str) -> Tuple[Optional[Any], Optional[str]]:
    try:
        return json.loads(raw), None
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, "error parsing %s: %s" % (label, exc)


def apply_mind_mode(b: dict, args: argparse.Namespace, now: str) -> None:
    """Update turns_since_operator_message and mind_mode from bump flags."""
    if args.operator_engaged:
        b["turns_since_operator_message"] = 0
        b["last_operator_message_at"] = now
        b["mind_mode"] = args.mode or "interactive"
        return
    if args.no_increment_silence:
        if args.mode:
            b["mind_mode"] = args.mode
        return
    tso = int(b.get("turns_since_operator_message") or 0) + 1
    b["turns_since_operator_message"] = tso
    if args.mode:
        b["mind_mode"] = args.mode
    elif tso >= 3:
        b["mind_mode"] = "autonomous"


def normalize_wake_runtime(record: dict) -> None:
    if not isinstance(record, dict):
        return
    if not isinstance(record.get("runtime"), dict):
        kind = record.get("runtime_kind") or ("tmux" if record.get("tmux_target") else None)
        target = record.get("runtime_target") or record.get("tmux_target")
        if kind and target:
            record["runtime"] = {"kind": kind, "target": target}
            if record.get("runtime_socket"):
                record["runtime"]["socket"] = record["runtime_socket"]
    for stale in ("runtime_kind", "runtime_target", "runtime_socket", "tmux_target"):
        record.pop(stale, None)


def normalize_wake_records(b: dict) -> None:
    wake = b.get("last_hand_wake")
    if not isinstance(wake, dict):
        return
    normalize_wake_runtime(wake)
    for record in ensure_dict(wake.get("by_hand")).values():
        normalize_wake_runtime(record)
    b.pop("last_hand_wake_target", None)


def apply_sensors_blob(b: dict, sensors: dict, args: argparse.Namespace) -> dict:
    """Extract fingerprint + side effects from a full fleet-sensors JSON blob."""
    b.pop("pane_classes", None)
    normalize_wake_records(b)
    fp = sensors.get("fingerprint")
    if not isinstance(fp, dict):
        fp = {}
    if args.runtime_states_json is None and sensors.get("runtime_states"):
        b["runtime_states"] = sensors["runtime_states"]
    if sensors.get("hand_progress"):
        b["hand_progress"] = sensors["hand_progress"]
    if isinstance(sensors.get("lane_progress"), dict):
        b["lane_progress"] = sensors["lane_progress"]
    if sensors.get("steward"):
        st = ensure_dict(b.get("steward"))
        st["armed"] = sensors["steward"].get("armed", st.get("armed"))
        st["tripped"] = sensors["steward"].get("tripped", st.get("tripped"))
        b["steward"] = st
    apply_head_report_state(b, sensors.get("heads"))
    return fp


def cmd_get(project: Path, baseline: Path) -> int:
    print(json.dumps(load_baseline(baseline), indent=2, ensure_ascii=False))
    return 0


def cmd_rearm_note(project: Path, baseline: Path) -> int:
    b = load_baseline(baseline)
    now = now_iso()
    ml = ensure_ml(b)
    ml["last_successful_cycle_at"] = now
    ml["last_cycle_ok"] = True
    b["mind_loop"] = ml
    # Cycle clock only — steward.last_rearm_at is steward.sh arm/rearm, not this.
    b["project"] = b.get("project") or str(project)
    save_json(baseline, b)
    print(json.dumps({"ok": True, "last_successful_cycle_at": now}, ensure_ascii=False))
    return 0


def cmd_bump(args: argparse.Namespace, project: Path, baseline: Path) -> int:
    b = load_baseline(baseline)
    normalize_wake_records(b)
    b.pop("pane_classes", None)
    now = now_iso()
    acted = bool(args.acted) and not bool(args.quiet)
    if args.quiet:
        acted = False

    b["version"] = b.get("version") or 1
    b["project"] = str(project)
    b["last_cycle"] = int(b.get("last_cycle") or 0) + 1
    b["last_cycle_at"] = now
    b["last_cycle_kind"] = args.kind or b.get("last_cycle_kind") or "superficial"
    b["last_cycle_summary"] = args.summary or ("sleep" if not acted else "acted")
    b["quiet_streak"] = 0 if acted else int(b.get("quiet_streak") or 0) + 1

    if args.mind_session is not None:
        args.operator_engaged = True
    apply_mind_mode(b, args, now)

    fp = None
    if args.fingerprint_file:
        try:
            raw = json.loads(Path(args.fingerprint_file).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            print("error reading fingerprint-file: %s" % exc, file=sys.stderr)
            return 1
        if isinstance(raw, dict) and isinstance(raw.get("fingerprint"), dict):
            fp = apply_sensors_blob(b, raw, args)
        else:
            fp = raw if isinstance(raw, dict) else {}
    elif args.fingerprint_json:
        fp, err = _parse_json_arg(args.fingerprint_json, "fingerprint-json")
        if err:
            print(err, file=sys.stderr)
            return 1

    if fp is not None:
        if isinstance(fp, dict):
            strip_legacy_head_fp_keys(fp)
        b["last_actionable_fingerprint"] = fp

    if args.runtime_states_json:
        data, err = _parse_json_arg(args.runtime_states_json, "runtime-states-json")
        if err:
            print(err, file=sys.stderr)
            return 1
        b["runtime_states"] = data

    if args.debt_json:
        data, err = _parse_json_arg(args.debt_json, "debt-json")
        if err:
            print(err, file=sys.stderr)
            return 1
        b["pending_debt"] = data

    if args.recap:
        recap = ensure_list(b.get("operator_recap"))
        recap.append(args.recap)
        b["operator_recap"] = recap[-50:]

    ml = ensure_ml(b)
    ml["last_successful_cycle_at"] = now
    ml["last_cycle_ok"] = True
    ml["last_cycle_acted"] = acted
    ml["last_wake_at"] = now

    if args.detach:
        b["mind_session"] = None
        ml["state"] = "detached"
        ml["detached_at"] = now
        ml["detach_reason"] = args.summary or "detach"
    elif args.mind_session is not None:
        b["mind_session"] = {
            "label": args.mind_session,
            "host": args.mind_host or platform.node(),
            "attached_at": now,
        }
        ml["state"] = "attached"
        ml["detached_at"] = None
        ml["detach_reason"] = None
    elif ml.get("state") in (None, "armed", "detached"):
        ml["state"] = "running"
    b["mind_loop"] = ml
    # Do not stamp steward.last_rearm_at here — that is steward.sh arm/rearm only.
    # Cycle success for dead-man is mind_loop.last_successful_cycle_at (above).

    save_json(baseline, b)
    print(
        json.dumps(
            {
                "ok": True,
                "last_cycle": b["last_cycle"],
                "last_cycle_at": now,
                "mind_mode": b.get("mind_mode"),
                "turns_since_operator_message": b.get("turns_since_operator_message"),
                "quiet_streak": b.get("quiet_streak"),
                "acted": acted,
                "summary": b.get("last_cycle_summary"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_wound_up(args: argparse.Namespace, project: Path, baseline: Path) -> int:
    b = load_baseline(baseline)
    now = now_iso()
    b["last_cycle"] = int(b.get("last_cycle") or 0) + 1
    b["last_cycle_at"] = now
    b["last_cycle_kind"] = "wind_down"
    b["last_cycle_summary"] = args.summary or "wound_up"
    b["project"] = str(project)
    dropped = [x.strip() for x in (args.dropped or "").split(",") if x.strip()]
    pcs = ensure_dict(b.get("runtime_states"))
    for name in dropped:
        pcs[name] = "stopped"
    b["runtime_states"] = pcs
    ml = ensure_ml(b)
    ml["state"] = "wound_up"
    ml["wound_up_at"] = now
    ml["last_successful_cycle_at"] = now
    ml["last_cycle_ok"] = True
    ml["last_cycle_acted"] = True
    ml["dropped_panes"] = dropped
    ml["handoff"] = args.handoff or (
        "Fleet wound up %s. Steward should be disarmed. "
        "Rearm: recreate panes + FLEET_CYCLE; steward only if operator enabled+asked."
        % now
    )
    b["mind_loop"] = ml
    st = ensure_dict(b.get("steward"))
    st["armed"] = False
    st["disarmed_at"] = now
    st["tripped"] = False
    b["steward"] = st
    recap = ensure_list(b.get("operator_recap"))
    recap.append("wind-down: %s" % b["last_cycle_summary"])
    b["operator_recap"] = recap[-50:]
    if args.fingerprint_json:
        data, err = _parse_json_arg(args.fingerprint_json, "fingerprint-json")
        if err:
            print(err, file=sys.stderr)
            return 1
        if isinstance(data, dict):
            strip_legacy_head_fp_keys(data)
        b["last_actionable_fingerprint"] = data
    save_json(baseline, b)
    print(json.dumps({"ok": True, "state": "wound_up", "at": now}, indent=2, ensure_ascii=False))
    return 0


def _extract_globals(argv: List[str]) -> Tuple[List[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Allow scope and baseline paths before or after the subcommand."""
    project = None  # type: Optional[str]
    baseline = None  # type: Optional[str]
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
        if a == "--baseline" and i + 1 < len(argv):
            baseline = argv[i + 1]
            i += 2
            continue
        if a.startswith("--baseline="):
            baseline = a.split("=", 1)[1]
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
    return out, project, baseline, fleet_id, fleet_file


def main(argv: Optional[List[str]] = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    rest, project_arg, baseline_arg, fleet_id_arg, fleet_file_arg = _extract_globals(raw)

    parent = argparse.ArgumentParser(add_help=False)
    add_fleet_scope_arguments(parent, required_project=False)
    parent.add_argument("--baseline", default=None, help="default: PROJECT/.vivi/mind-baseline.json")

    ap = argparse.ArgumentParser(
        description="Fleet mind-baseline.json helper (Python 3.9+; macOS/Linux)",
        epilog=(
            "Examples:\n"
            "  fleet-baseline.py --project $ROOT get\n"
            "  fleet-baseline.py get --project $ROOT\n"
            "  fleet-baseline.py bump -p $ROOT -s 'sleep' --quiet\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True  # type: ignore[attr-defined]

    sub.add_parser("get", parents=[parent], help="Print baseline JSON")

    p_bump = sub.add_parser("bump", parents=[parent], help="Increment cycle counters after a FLEET_CYCLE")
    p_bump.add_argument("--summary", "-s", required=True)
    p_bump.add_argument("--acted", action="store_true", help="Cycle took board/ops action")
    p_bump.add_argument("--quiet", action="store_true", help="Quiet sleep cycle")
    p_bump.add_argument("--mode", choices=["interactive", "autonomous"])
    p_bump.add_argument("--kind", default="superficial")
    p_bump.add_argument("--fingerprint-file", help="sensors JSON from fleet-sensors.py")
    p_bump.add_argument("--fingerprint-json")
    p_bump.add_argument("--runtime-states-json")
    p_bump.add_argument("--debt-json")
    p_bump.add_argument("--recap", help="Append one operator_recap line")
    p_bump.add_argument("--operator-engaged", action="store_true", help="Reset silence counters")
    p_bump.add_argument(
        "--no-increment-silence",
        action="store_true",
        help="Do not += turns_since_operator_message (caller already resolved mode)",
    )
    p_bump.add_argument("--mind-session", default=None, metavar="LABEL",
        help="Attach Mind: set mind_session label (implies --operator-engaged)")
    p_bump.add_argument("--mind-host", default=None, metavar="HOST",
        help="Hostname for mind_session (default: platform.node())")
    p_bump.add_argument("--detach", action="store_true",
        help="Detach Mind: clear mind_session, set state=detached")

    sub.add_parser("rearm-note", parents=[parent], help="Touch last_successful_cycle_at only")

    p_w = sub.add_parser("wound-up", parents=[parent], help="Mark fleet wound down")
    p_w.add_argument("--summary", "-s", default="wound_up")
    p_w.add_argument("--dropped", default="", help="comma pane names marked down")
    p_w.add_argument("--handoff", default=None)
    p_w.add_argument("--fingerprint-json", default=None)

    args = ap.parse_args(rest)
    project_s = project_arg or args.project
    if not project_s:
        ap.error("--project/-p is required (before or after the subcommand)")
    baseline_s = baseline_arg or args.baseline

    project = Path(project_s).expanduser().resolve()
    if not project.is_dir():
        print("error: project is not a directory: %s" % project, file=sys.stderr)
        return 1
    try:
        resolve_fleet_file(
            project,
            fleet_id_arg or args.fleet,
            fleet_file_arg or args.fleet_file,
        )
    except FleetScopeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    baseline = (
        Path(baseline_s).expanduser().resolve()
        if baseline_s
        else project / ".vivi" / "mind-baseline.json"
    )

    if args.cmd == "get":
        return cmd_get(project, baseline)
    if args.cmd == "rearm-note":
        return cmd_rearm_note(project, baseline)
    if args.cmd == "bump":
        return cmd_bump(args, project, baseline)
    if args.cmd == "wound-up":
        return cmd_wound_up(args, project, baseline)
    return 1


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
