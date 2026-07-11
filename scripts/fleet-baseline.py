#!/usr/bin/env python3
"""Read/update fleet mind-baseline.json for FLEET_CYCLE bookkeeping.

  fleet-baseline.py [--project <root>] get
  fleet-baseline.py get --project <root>
  fleet-baseline.py bump -p <root> --summary '…' [--acted|--quiet] \\
      [--mode interactive|autonomous] [--kind superficial|thorough|wind_down] \\
      [--fingerprint-file sensors.json] [--fingerprint-json '{…}'] \\
      [--pane-classes-json '{…}'] [--debt-json '[…]'] [--recap 'line'] \\
      [--operator-engaged] [--no-increment-silence]
  fleet-baseline.py rearm-note -p <root>   # touch last_successful_cycle_at only
  fleet-baseline.py wound-up -p <root> --summary '…' [--dropped hand-1,hand-2]

--project/-p may appear before or after the subcommand.

Exit: 0 ok · 1 error
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path) -> dict:
    if not path.is_file():
        return {"version": 1, "project": str(path.parent.parent)}
    try:
        return json.loads(path.read_text())
    except Exception as e:
        print(f"error reading baseline: {e}", file=sys.stderr)
        sys.exit(1)


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def ensure_ml(b: dict) -> dict:
    ml = b.get("mind_loop")
    if not isinstance(ml, dict):
        ml = {}
        b["mind_loop"] = ml
    return ml


def cmd_get(project: Path, baseline: Path) -> int:
    b = load(baseline)
    print(json.dumps(b, indent=2))
    return 0


def cmd_rearm_note(project: Path, baseline: Path) -> int:
    b = load(baseline)
    now = now_iso()
    ml = ensure_ml(b)
    ml["last_successful_cycle_at"] = now
    ml["last_cycle_ok"] = True
    st = b.get("steward") if isinstance(b.get("steward"), dict) else {}
    st["last_rearm_at"] = now
    b["steward"] = st
    b["project"] = b.get("project") or str(project)
    save(baseline, b)
    print(json.dumps({"ok": True, "last_successful_cycle_at": now}))
    return 0


def cmd_bump(args: argparse.Namespace, project: Path, baseline: Path) -> int:
    b = load(baseline)
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

    # mode / operator silence
    if args.operator_engaged:
        b["turns_since_operator_message"] = 0
        b["last_operator_message_at"] = now
        b["mind_mode"] = args.mode or "interactive"
    elif args.no_increment_silence:
        if args.mode:
            b["mind_mode"] = args.mode
    else:
        # FLEET_CYCLE-only default: increment silence
        tso = int(b.get("turns_since_operator_message") or 0) + 1
        b["turns_since_operator_message"] = tso
        if args.mode:
            b["mind_mode"] = args.mode
        elif tso >= 3:
            b["mind_mode"] = "autonomous"
        # else keep prior mind_mode

    if args.mode and args.operator_engaged is False and args.no_increment_silence:
        b["mind_mode"] = args.mode

    fp = None
    if args.fingerprint_file:
        fp = json.loads(Path(args.fingerprint_file).read_text())
        if "fingerprint" in fp and isinstance(fp["fingerprint"], dict):
            # full sensors dump
            sensors = fp
            fp = sensors["fingerprint"]
            if args.pane_classes_json is None and sensors.get("pane_classes"):
                b["pane_classes"] = sensors["pane_classes"]
            if sensors.get("steward"):
                st = b.get("steward") if isinstance(b.get("steward"), dict) else {}
                st["armed"] = sensors["steward"].get("armed", st.get("armed"))
                st["tripped"] = sensors["steward"].get("tripped", st.get("tripped"))
                b["steward"] = st
    elif args.fingerprint_json:
        fp = json.loads(args.fingerprint_json)
    if fp is not None:
        b["last_actionable_fingerprint"] = fp

    if args.pane_classes_json:
        b["pane_classes"] = json.loads(args.pane_classes_json)

    if args.debt_json:
        b["pending_debt"] = json.loads(args.debt_json)

    if args.recap:
        recap = b.get("operator_recap") if isinstance(b.get("operator_recap"), list) else []
        recap.append(args.recap)
        b["operator_recap"] = recap[-50:]

    ml = ensure_ml(b)
    ml["last_successful_cycle_at"] = now
    ml["last_cycle_ok"] = True
    ml["last_cycle_acted"] = acted
    ml["last_wake_at"] = now
    if ml.get("state") in (None, "armed", "detached"):
        ml["state"] = "running"
    b["mind_loop"] = ml

    st = b.get("steward") if isinstance(b.get("steward"), dict) else {}
    st["last_rearm_at"] = now
    b["steward"] = st

    save(baseline, b)
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
        )
    )
    return 0


def cmd_wound_up(args: argparse.Namespace, project: Path, baseline: Path) -> int:
    b = load(baseline)
    now = now_iso()
    b["last_cycle"] = int(b.get("last_cycle") or 0) + 1
    b["last_cycle_at"] = now
    b["last_cycle_kind"] = "wind_down"
    b["last_cycle_summary"] = args.summary or "wound_up"
    b["project"] = str(project)
    dropped = [x.strip() for x in (args.dropped or "").split(",") if x.strip()]
    pcs = b.get("pane_classes") if isinstance(b.get("pane_classes"), dict) else {}
    for d in dropped:
        pcs[d] = "down"
    b["pane_classes"] = pcs
    ml = ensure_ml(b)
    ml["state"] = "wound_up"
    ml["wound_up_at"] = now
    ml["last_successful_cycle_at"] = now
    ml["last_cycle_ok"] = True
    ml["last_cycle_acted"] = True
    ml["dropped_panes"] = dropped
    ml["handoff"] = args.handoff or (
        f"Fleet wound up {now}. Steward should be disarmed. Rearm: steward.sh arm + recreate panes + FLEET_CYCLE."
    )
    b["mind_loop"] = ml
    st = b.get("steward") if isinstance(b.get("steward"), dict) else {}
    st["armed"] = False
    st["disarmed_at"] = now
    st["tripped"] = False
    b["steward"] = st
    recap = b.get("operator_recap") if isinstance(b.get("operator_recap"), list) else []
    recap.append(f"wind-down: {b['last_cycle_summary']}")
    b["operator_recap"] = recap[-50:]
    if args.fingerprint_json:
        b["last_actionable_fingerprint"] = json.loads(args.fingerprint_json)
    save(baseline, b)
    print(json.dumps({"ok": True, "state": "wound_up", "at": now}, indent=2))
    return 0


def _extract_globals(argv: list[str]) -> tuple[list[str], str | None, str | None]:
    """Allow --project / --baseline before *or* after the subcommand.

    Returns (remaining_argv, project, baseline).
    """
    project: str | None = None
    baseline: str | None = None
    out: list[str] = []
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
        out.append(a)
        i += 1
    return out, project, baseline


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    rest, project_arg, baseline_arg = _extract_globals(raw)

    parent = argparse.ArgumentParser(add_help=False)
    # project may already be extracted; keep optional here so subcommands don't double-require
    parent.add_argument("--project", "-p", default=None)
    parent.add_argument("--baseline", default=None, help="default: PROJECT/.vivi/mind-baseline.json")

    ap = argparse.ArgumentParser(
        description="Fleet mind-baseline.json helper",
        epilog=(
            "Examples:\n"
            "  fleet-baseline.py --project $ROOT get\n"
            "  fleet-baseline.py get --project $ROOT\n"
            "  fleet-baseline.py bump -p $ROOT -s 'sleep' --quiet\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("get", parents=[parent], help="Print baseline JSON")

    p_bump = sub.add_parser("bump", parents=[parent], help="Increment cycle counters after a FLEET_CYCLE")
    p_bump.add_argument("--summary", "-s", required=True)
    p_bump.add_argument("--acted", action="store_true", help="Cycle took board/ops action")
    p_bump.add_argument("--quiet", action="store_true", help="Quiet sleep cycle")
    p_bump.add_argument("--mode", choices=["interactive", "autonomous"])
    p_bump.add_argument("--kind", default="superficial")
    p_bump.add_argument("--fingerprint-file", help="sensors JSON from fleet-sensors.py")
    p_bump.add_argument("--fingerprint-json")
    p_bump.add_argument("--pane-classes-json")
    p_bump.add_argument("--debt-json")
    p_bump.add_argument("--recap", help="Append one operator_recap line")
    p_bump.add_argument("--operator-engaged", action="store_true", help="Reset silence counters")
    p_bump.add_argument(
        "--no-increment-silence",
        action="store_true",
        help="Do not += turns_since_operator_message (caller already resolved mode)",
    )

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

    project = Path(project_s).resolve()
    baseline = Path(baseline_s) if baseline_s else project / ".vivi" / "mind-baseline.json"

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
    sys.exit(main())
