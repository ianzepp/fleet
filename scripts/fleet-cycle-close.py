#!/usr/bin/env python3
"""Close a Mind cycle with a durable sensor/disposition receipt.

One cycle-close operation collects canonical fleet sensors, requires an explicit
disposition for every signal, records the redacted sensor observation, persists
the baseline, writes a per-cycle close receipt, and optionally tracks
steward state. It does not duplicate the atomic successful-wake
recording.

  fleet-cycle-close.py --project <root> --acted [--summary '…'] \
      --disposition 'growth_refill_required=delegated:task abc123 filed to head-ceo'
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

Disposition values are acted, delegated, escalated, deferred-valid, or
sleep-valid. Evidence after the colon is required. A JSON object may be supplied
with --dispositions-file instead of repeated flags.

Steward: rearms only when fleet.json steward.enabled==true and baseline
steward.armed==true.  Does NOT enable or arm steward.

Preserves last_hand_wake data (baseline bump reads only
the fingerprint/runtime/head fields from the sensors blob).

Requires: Python 3.9+ (macOS / Linux). Exit: 0 ok · 1 error · 2 usage.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    FleetScopeError,
    add_fleet_scope_arguments,
    ensure_dict,
    load_json,
    now_iso as _now_iso,
    require_python,
    resolve_fleet_file,
    run_cmd,
)

require_python()

ALLOWED_DISPOSITIONS = frozenset(
    ("acted", "delegated", "escalated", "deferred-valid", "sleep-valid")
)


def now_iso() -> str:
    return _now_iso()


def _find_scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def _load_sensors_module() -> Any:
    path = _find_scripts_dir() / "fleet-sensors.py"
    spec = importlib.util.spec_from_file_location("fleet_sensors_closeout", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load fleet-sensors.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_disposition(signal: str, value: Any) -> Dict[str, str]:
    if isinstance(value, str):
        kind, separator, evidence = value.partition(":")
    elif isinstance(value, dict):
        kind = str(value.get("disposition") or value.get("status") or "")
        evidence = str(value.get("evidence") or "")
        separator = ":" if evidence else ""
    else:
        raise ValueError("disposition for %s must be a string or object" % signal)
    kind = kind.strip()
    evidence = evidence.strip()
    if kind not in ALLOWED_DISPOSITIONS:
        raise ValueError(
            "disposition for %s must be one of %s"
            % (signal, ", ".join(sorted(ALLOWED_DISPOSITIONS)))
        )
    if not separator or not evidence:
        raise ValueError("disposition for %s requires non-empty evidence" % signal)
    return {"signal": signal, "disposition": kind, "evidence": evidence}


def parse_dispositions(values: List[str], file_path: Optional[str]) -> Dict[str, Dict[str, str]]:
    raw: Dict[str, Any] = {}
    if file_path:
        path = Path(file_path).expanduser().resolve()
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("cannot read dispositions file %s: %s" % (path, exc))
        if not isinstance(loaded, dict):
            raise ValueError("dispositions file must contain a JSON object")
        raw.update(loaded)
    for item in values:
        signal, separator, value = item.partition("=")
        signal = signal.strip()
        if not separator or not signal:
            raise ValueError("--disposition must be SIGNAL=KIND:EVIDENCE")
        if signal in raw:
            raise ValueError("duplicate disposition for %s" % signal)
        raw[signal] = value
    return {signal: _normalize_disposition(signal, value) for signal, value in raw.items()}


def validate_dispositions(
    sensor_data: Dict[str, Any], dispositions: Dict[str, Dict[str, str]], quiet: bool
) -> List[Dict[str, str]]:
    required = {str(signal) for signal in sensor_data.get("signals") or []}
    if sensor_data.get("partial"):
        required.add("sensors_partial")
    provided = set(dispositions)
    missing = sorted(required - provided)
    extra = sorted(provided - required)
    if missing:
        raise ValueError("unresolved sensor signals: %s" % ", ".join(missing))
    if extra:
        raise ValueError("dispositions supplied for absent signals: %s" % ", ".join(extra))
    ordered = [dispositions[signal] for signal in sorted(required)]
    if quiet:
        active = [
            row["signal"]
            for row in ordered
            if row["disposition"] not in ("deferred-valid", "sleep-valid")
        ]
        if active:
            raise ValueError("quiet cycle has active dispositions: %s" % ", ".join(active))
    return ordered


def cmd_close(args: argparse.Namespace, project: Path) -> int:
    scripts = _find_scripts_dir()
    try:
        fleet_path_obj, _ = resolve_fleet_file(project, args.fleet, args.fleet_file)
    except FleetScopeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    baseline_path = args.baseline
    if baseline_path:
        baseline_path_obj = Path(baseline_path).expanduser().resolve()
    else:
        baseline_path_obj = project / ".vivi" / "mind-baseline.json"

    if not fleet_path_obj.is_file():
        print("error: fleet.json not found at %s" % fleet_path_obj, file=sys.stderr)
        return 1

    fleet = load_json(fleet_path_obj)
    baseline_before = load_json(baseline_path_obj)
    try:
        current_cycle = int(baseline_before.get("last_cycle") or 0)
    except (TypeError, ValueError):
        print("error: baseline last_cycle is not an integer", file=sys.stderr)
        return 1
    cycle_id = current_cycle + 1

    # 1. Run fleet-sensors.py
    sensors_cmd = [
        sys.executable,
        str(scripts / "fleet-sensors.py"),
        "--project", str(project),
    ]
    if args.fleet:
        sensors_cmd.extend(["--fleet", args.fleet])
    if args.fleet_file:
        sensors_cmd.extend(["--fleet-file", args.fleet_file])
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
        try:
            sensor_data = json.loads(sensors_blob)
        except json.JSONDecodeError:
            print("error: fleet-sensors.py did not produce valid JSON", file=sys.stderr)
            return 1
        if not isinstance(sensor_data, dict):
            print("error: fleet-sensors.py output must be a JSON object", file=sys.stderr)
            return 1
        sensor_data["partial"] = bool(sensor_data.get("partial") or sensors_partial)
        observed_baseline = sensor_data.get("baseline_last_cycle")
        if observed_baseline is not None and observed_baseline != current_cycle:
            print(
                "error: sensor/baseline race: expected last_cycle %s, observed %s"
                % (current_cycle, observed_baseline),
                file=sys.stderr,
            )
            return 1
    else:
        print("error: fleet-sensors.py produced empty output", file=sys.stderr)
        return 1

    try:
        dispositions = parse_dispositions(args.disposition, args.dispositions_file)
        disposition_rows = validate_dispositions(sensor_data, dispositions, args.quiet)
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    # Record the exact collected observation before advancing the baseline. The
    # sensor logger redacts pane/mail content according to fleet.json policy.
    sensor_module = _load_sensors_module()
    log_config = sensor_module.sensor_log_config(fleet, project)
    sensor_log = {"status": "disabled", "level": log_config.get("level")}
    if log_config.get("enabled") and log_config.get("level") != "off":
        try:
            sensor_log.update(
                sensor_module.record_history(
                    sensor_data, log_config, str(cycle_id), str(sensor_data.get("at") or now_iso())
                )
            )
        except (OSError, UnicodeError, ValueError, TypeError) as exc:
            print("error: cannot record canonical sensor history: %s" % exc, file=sys.stderr)
            return 1

    summary = args.summary or ("acted" if args.acted else "sleep")
    receipt = {
        "schema_version": 1,
        "status": "prepared",
        "cycle_id": cycle_id,
        "prepared_at": now_iso(),
        "acted": args.acted,
        "quiet": args.quiet,
        "summary": summary,
        "kind": args.kind or "superficial",
        "operator_engaged": bool(args.operator_engaged),
        "sensors_partial": sensors_partial,
        "no_watch": args.no_watch,
        "sensor_at": sensor_data.get("at"),
        "sensor_log": sensor_log,
        "sensor_observation": sensor_module.summary_snapshot(sensor_data),
        "dispositions": disposition_rows,
        "unresolved_signals": [],
        "baseline_before": {
            "last_cycle": current_cycle,
            "mind_mode": baseline_before.get("mind_mode"),
            "turns_since_operator_message": baseline_before.get("turns_since_operator_message"),
            "quiet_streak": baseline_before.get("quiet_streak"),
        },
    }
    if args.recap:
        receipt["recap"] = args.recap
    receipt_path = project / ".vivi" / "logs" / "cycles" / ("%s.json" % cycle_id)
    existing_receipt = load_json(receipt_path) if receipt_path.exists() else {}
    if existing_receipt.get("status") == "closed":
        print("error: cycle receipt already closed at %s" % receipt_path, file=sys.stderr)
        return 1
    _write_atomic(receipt_path, receipt)
    fingerprint_file = tempfile_name(sensors_blob)

    try:
        # Advance the baseline only after sensor history and the prepared receipt exist.
        bump_cmd = [
            sys.executable,
            str(scripts / "fleet-baseline.py"),
            "bump",
            "-p", str(project),
            "-s", summary,
        ]
        if args.fleet:
            bump_cmd += ["--fleet", args.fleet]
        if args.fleet_file:
            bump_cmd += ["--fleet-file", args.fleet_file]
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

    # Steward rearm was handled by steward.sh (now removed).
    # Steward state (enabled/armed/tripped) is still tracked in baseline
    # and surfaced by sensors, but the rearm action is a no-op.
    # If steward is re-enabled in the future, rearm via a Vivi-native path.

    # Finalize the per-cycle receipt and update the latest-close pointer.
    updated = load_json(baseline_path_obj)
    if updated.get("last_cycle") != cycle_id:
        print(
            "error: baseline advanced to unexpected cycle %s (expected %s)"
            % (updated.get("last_cycle"), cycle_id),
            file=sys.stderr,
        )
        return 1
    receipt["status"] = "closed"
    receipt["closed_at"] = now_iso()
    receipt["steward_rearmed"] = steward_rearmed
    receipt["baseline_after"] = {
        "last_cycle": updated.get("last_cycle"),
        "mind_mode": updated.get("mind_mode"),
        "turns_since_operator_message": updated.get("turns_since_operator_message"),
        "quiet_streak": updated.get("quiet_streak"),
    }
    _write_atomic(receipt_path, receipt)

    closure_path = project / ".vivi" / "cycle-closure.json"
    _write_atomic(closure_path, receipt)

    print(json.dumps({"ok": True, "cycle": cycle_id, "closed_at": receipt["closed_at"],
                      "receipt": str(receipt_path)},
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
    add_fleet_scope_arguments(p)
    p.add_argument("--baseline", help="mind-baseline.json path (default: PROJECT/.vivi/mind-baseline.json)")

    act_group = p.add_mutually_exclusive_group(required=True)
    act_group.add_argument("--acted", action="store_true", help="Cycle took board/ops action")
    act_group.add_argument("--quiet", action="store_true", help="Quiet sleep cycle")

    p.add_argument("--summary", "-s", default=None, help="one-line cycle description")
    p.add_argument(
        "--disposition",
        action="append",
        default=[],
        metavar="SIGNAL=KIND:EVIDENCE",
        help="explicit sensor disposition; repeat once per emitted signal",
    )
    p.add_argument(
        "--dispositions-file",
        default=None,
        metavar="PATH",
        help="JSON object mapping signal names to disposition/evidence",
    )
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
