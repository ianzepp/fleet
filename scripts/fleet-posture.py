#!/usr/bin/env python3
"""Inspect or atomically change a Fleet posture.

  fleet-posture.py get --project <root> [--json]
  fleet-posture.py set --project <root> growth|standby|dormant \
      --reason 'why' [--wake-trigger '...']... [--json]

The helper updates only fleet.json.fleet_posture, validates the candidate with
verify-fleet-json.py --strict, then atomically replaces fleet.json. Existing
wake_triggers and optional posture fields are preserved unless explicitly
replaced. It does not wake roles, run sensors, bump the Mind baseline, or arm the
steward; the next Mind cycle observes the new source-of-truth posture.

Requires: Python 3.9+ (macOS / Linux). Exit: 0 ok · 1 data/validation error ·
2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

MODES = ("growth", "standby", "dormant")
ALIASES = {"campaign": "growth", "active": "growth", "on_call": "standby", "on-call": "standby"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_object(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read %s: %s" % (path, exc)) from exc
    if not isinstance(value, dict):
        raise ValueError("%s root must be a JSON object" % path)
    return value


def normalize_mode(raw: str) -> str:
    mode = ALIASES.get(raw.lower(), raw.lower())
    if mode not in MODES:
        raise ValueError("posture must be one of: %s" % ", ".join(MODES))
    return mode


def posture_of(fleet: Dict[str, Any]) -> Dict[str, Any]:
    raw = fleet.get("fleet_posture")
    posture = dict(raw) if isinstance(raw, dict) else {}
    posture["mode"] = normalize_mode(str(posture.get("mode") or "growth"))
    return posture


def print_posture(path: Path, posture: Dict[str, Any], as_json: bool, changed: bool = False) -> None:
    if as_json:
        print(json.dumps({"ok": True, "changed": changed, "fleet": str(path), "fleet_posture": posture}, indent=2))
        return
    print("posture %s" % posture.get("mode"))
    print("reason  %s" % (posture.get("reason") or ""))
    print("since   %s" % (posture.get("since") or ""))
    triggers = posture.get("wake_triggers")
    if isinstance(triggers, list):
        for trigger in triggers:
            print("wake    %s" % trigger)


def validate_candidate(candidate: Path, script_dir: Path) -> None:
    verifier = script_dir / "verify-fleet-json.py"
    result = subprocess.run(
        [sys.executable, str(verifier), "--fleet", str(candidate), "--strict"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("candidate failed strict validation:\n%s" % result.stdout.rstrip())


def save_atomic(path: Path, fleet: Dict[str, Any], script_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    candidate = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(fleet, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        validate_candidate(candidate, script_dir)
        os.replace(str(candidate), str(path))
    finally:
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Inspect or atomically change fleet posture")
    p.add_argument("command", choices=("get", "set"))
    p.add_argument("mode", nargs="?", help="growth, standby, or dormant (set only)")
    p.add_argument("--project", "-p", required=True, help="fleet project root")
    p.add_argument("--fleet", help="fleet.json path (default: PROJECT/.vivi/fleet.json)")
    p.add_argument("--reason", help="one-line posture reason (set only)")
    p.add_argument("--wake-trigger", action="append", default=None, help="replace wake triggers; repeatable")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "get" and args.mode is not None:
        parser().error("get does not accept a mode")
    if args.command == "set" and args.mode is None:
        parser().error("set requires a posture mode")
    project = Path(args.project).expanduser().resolve()
    path = Path(args.fleet).expanduser().resolve() if args.fleet else project / ".vivi" / "fleet.json"
    try:
        fleet = load_object(path)
        current = posture_of(fleet)
        if args.command == "get":
            print_posture(path, current, args.json)
            return 0
        mode = normalize_mode(args.mode)
        updated = dict(current)
        updated["mode"] = mode
        updated["since"] = now_iso()
        if args.reason is not None:
            reason = args.reason.strip()
            if not reason:
                raise ValueError("--reason must not be empty")
            updated["reason"] = reason
        if args.wake_trigger is not None:
            triggers = [item.strip() for item in args.wake_trigger]
            if not triggers or any(not item for item in triggers):
                raise ValueError("--wake-trigger values must not be empty")
            updated["wake_triggers"] = triggers
        fleet["fleet_posture"] = updated
        save_atomic(path, fleet, Path(__file__).resolve().parent)
        print_posture(path, updated, args.json, changed=(updated != current))
        return 0
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
