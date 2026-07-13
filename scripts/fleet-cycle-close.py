#!/usr/bin/env python3
"""Close a Mind cycle: run sensors, persist to baseline, optionally rearm steward.

One cycle-close operation collects canonical fleet sensors, persists exact
fingerprint / runtime states / head report data into the Mind baseline, and
optionally rearms the steward dead-man. It does not duplicate fleet-doorbell.sh's
atomic successful-wake recording.

  fleet-cycle-close.py --project <root> --acted [--summary '…']
  fleet-cycle-close.py --project <root> --quiet [--summary '…']
  fleet-cycle-close.py --project <root> --acted --operator-engaged --kind thorough \\
      --recap 'Merged theme alpha, filed two new units'

Flags inherited from fleet-baseline.py bump:
  --acted / --quiet     required, mutually exclusive
  --summary             one-line cycle description
  --kind                superficial (default) or thorough
  --mode                interactive or autonomous
  --operator-engaged    reset turns_since_operator_message to 0
  --recap               append one operator_recap line
  --no-watch            skip Vivi mailspace watch in sensors
  --no-increment-silence  do not += turns_since_operator_message

Steward: rearms only when fleet.json steward.enabled==true and baseline
steward.armed==true.  Does NOT enable or arm steward.

Preserves fleet-doorbell.sh last_hand_wake data (baseline bump reads only
the fingerprint/runtime/head fields from the sensors blob).

Requires: Python 3.9+ (macOS / Linux). Exit: 0 ok · 1 error · 2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    ensure_dict,
    load_json,
    now_iso as _now_iso,
    require_python,
    run_cmd,
)

require_python()


def now_iso() -> str:
    return _now_iso()


def _find_scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def cmd_close(args: argparse.Namespace, project: Path) -> int:
    scripts = _find_scripts_dir()
    fleet_path = args.fleet
    if fleet_path:
        fleet_path_obj = Path(fleet_path).expanduser().resolve()
    else:
        fleet_path_obj = project / ".vivi" / "fleet.json"

    baseline_path = args.baseline
    if baseline_path:
        baseline_path_obj = Path(baseline_path).expanduser().resolve()
    else:
        baseline_path_obj = project / ".vivi" / "mind-baseline.json"

    if not fleet_path_obj.is_file():
        print("error: fleet.json not found at %s" % fleet_path_obj, file=sys.stderr)
        return 1

    # 1. Run fleet-sensors.py
    sensors_cmd = [
        sys.executable,
        str(scripts / "fleet-sensors.py"),
        "--project", str(project),
    ]
    if args.no_watch:
        sensors_cmd.append("--no-watch")
    if args.sensors_text:
        sensors_cmd.append("--text")

    sensor_result = subprocess.run(
        sensors_cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    # sensors exit 2 is partial — still usable; exit 1 is hard error
    if sensor_result.returncode == 1:
        print("error: fleet-sensors.py failed", file=sys.stderr)
        if sensor_result.stderr:
            print(sensor_result.stderr, file=sys.stderr)
        return 1

    sensors_partial = sensor_result.returncode == 2
    if sensors_partial:
        print("warning: fleet-sensors.py returned partial (exit 2)", file=sys.stderr)

    # Write sensors output to a temp file for fleet-baseline.py bump
    sensors_blob = sensor_result.stdout
    fingerprint_file = None
    if sensors_blob.strip():
        # Validate it's parseable JSON
        try:
            json.loads(sensors_blob)
        except json.JSONDecodeError:
            print("error: fleet-sensors.py did not produce valid JSON", file=sys.stderr)
            return 1

        fingerprint_file = tempfile_name(sensors_blob)
    else:
        print("error: fleet-sensors.py produced empty output", file=sys.stderr)
        return 1

    try:
        # 2. Run fleet-baseline.py bump
        summary = args.summary or ("acted" if args.acted else "sleep")
        bump_cmd = [
            sys.executable,
            str(scripts / "fleet-baseline.py"),
            "bump",
            "-p", str(project),
            "-s", summary,
        ]
        if args.acted:
            bump_cmd.append("--acted")
        if args.quiet:
            bump_cmd.append("--quiet")
        if args.kind:
            bump_cmd += ["--kind", args.kind]
        if args.mode:
            bump_cmd += ["--mode", args.mode]
        if args.operator_engaged:
            bump_cmd.append("--operator-engaged")
        if args.no_increment_silence:
            bump_cmd.append("--no-increment-silence")
        if args.recap:
            bump_cmd += ["--recap", args.recap]
        if fingerprint_file:
            bump_cmd += ["--fingerprint-file", fingerprint_file]
        if args.runtime_states_json:
            bump_cmd += ["--runtime-states-json", args.runtime_states_json]
        if args.debt_json:
            bump_cmd += ["--debt-json", args.debt_json]
        if args.mind_session:
            bump_cmd += ["--mind-session", args.mind_session]
        if args.mind_host:
            bump_cmd += ["--mind-host", args.mind_host]
        if args.detach:
            bump_cmd.append("--detach")

        bump_result = subprocess.run(
            bump_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if bump_result.returncode != 0:
            print("error: fleet-baseline.py bump failed", file=sys.stderr)
            if bump_result.stderr:
                print(bump_result.stderr, file=sys.stderr)
            return 1
        print(bump_result.stdout.strip())
    finally:
        if fingerprint_file and os.path.exists(fingerprint_file):
            try:
                os.unlink(fingerprint_file)
            except OSError:
                pass

    # 3. Steward rearm (only if enabled+armed)
    fleet = load_json(fleet_path_obj)
    baseline = load_json(baseline_path_obj)

    steward_config = fleet.get("steward") if isinstance(fleet.get("steward"), dict) else {}
    steward_enabled = steward_config.get("enabled", False)
    steward_baseline = baseline.get("steward") if isinstance(baseline.get("steward"), dict) else {}
    steward_armed = steward_baseline.get("armed", False)

    if steward_enabled and steward_armed:
        steward_cmd = [
            str(scripts / "steward.sh"),
            "rearm",
            "--project", str(project),
        ]
        steward_result = subprocess.run(
            steward_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if steward_result.returncode == 0:
            print("steward rearmed")
        else:
            print("warning: steward.sh rearm failed (rc=%d)" % steward_result.returncode,
                  file=sys.stderr)
            if steward_result.stderr:
                print(steward_result.stderr.strip(), file=sys.stderr)
    elif steward_enabled and not steward_armed:
        print("info: steward enabled but not armed — skipping rearm")
    # else: steward disabled — no output (silent skip)

    # 4. Write closure record
    closure = {
        "closed_at": now_iso(),
        "acted": args.acted,
        "quiet": args.quiet,
        "summary": summary,
        "kind": args.kind or "superficial",
        "operator_engaged": bool(args.operator_engaged),
        "sensors_partial": sensors_partial,
        "no_watch": args.no_watch,
        "steward_rearmed": steward_enabled and steward_armed,
    }
    if args.recap:
        closure["recap"] = args.recap

    # Read the updated baseline for cycle id
    updated = load_json(baseline_path_obj)
    closure["last_cycle"] = updated.get("last_cycle")
    closure["mind_mode"] = updated.get("mind_mode")
    closure["turns_since_operator_message"] = updated.get("turns_since_operator_message")
    closure["quiet_streak"] = updated.get("quiet_streak")

    closure_path = project / ".vivi" / "cycle-closure.json"
    _write_atomic(closure_path, closure)

    print(json.dumps({"ok": True, "cycle": closure.get("last_cycle"), "closed_at": closure["closed_at"]},
                     ensure_ascii=False))
    return 0


import tempfile as _tempfile_module  # noqa: E402 — keep top-level imports clean


def tempfile_name(content: str) -> str:
    """Write content to a temp file and return its path. Caller must clean up."""
    fd, name = _tempfile_module.mkstemp(
        prefix="fleet-sensors-", suffix=".json",
    )
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(content)
    return name


def _write_atomic(path: Path, data: dict) -> None:
    """Atomically write JSON to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = _tempfile_module.mkstemp(
        prefix=".%s." % path.name,
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Close a Mind cycle: sensors → baseline → optional steward rearm.",
    )
    p.add_argument("--project", "-p", required=True, help="fleet project root")
    p.add_argument("--fleet", help="fleet.json path (default: PROJECT/.vivi/fleet.json)")
    p.add_argument("--baseline", help="mind-baseline.json path (default: PROJECT/.vivi/mind-baseline.json)")

    act_group = p.add_mutually_exclusive_group(required=True)
    act_group.add_argument("--acted", action="store_true", help="Cycle took board/ops action")
    act_group.add_argument("--quiet", action="store_true", help="Quiet sleep cycle")

    p.add_argument("--summary", "-s", default=None, help="one-line cycle description")
    p.add_argument("--kind", default=None, choices=["superficial", "thorough"],
                   help="cycle kind (default: superficial)")
    p.add_argument("--mode", default=None, choices=["interactive", "autonomous"],
                   help="mind mode override")
    p.add_argument("--operator-engaged", action="store_true",
                   help="Reset silence counters (human prose detected)")
    p.add_argument("--recap", default=None, help="append one operator_recap line")
    p.add_argument("--no-watch", action="store_true",
                   help="skip Vivi mailspace watch in sensors")
    p.add_argument("--no-increment-silence", action="store_true",
                   help="do not += turns_since_operator_message")
    p.add_argument("--sensors-text", action="store_true",
                   help="request text output from sensors (still consumes JSON for baseline)")
    p.add_argument("--runtime-states-json", default=None,
                   help="explicit runtime states JSON (overrides sensors)")
    p.add_argument("--debt-json", default=None,
                   help="explicit pending debt JSON")
    p.add_argument("--mind-session", default=None, metavar="LABEL",
                   help="attach Mind: set mind_session label (implies --operator-engaged)")
    p.add_argument("--mind-host", default=None, metavar="HOST",
                   help="hostname for mind_session")
    p.add_argument("--detach", action="store_true",
                   help="detach Mind: clear mind_session, set state=detached")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print("error: project is not a directory: %s" % project, file=sys.stderr)
        return 1

    # if --acted and --quiet are both set, argparse mutually_exclusive_group handles it
    return cmd_close(args, project)


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
