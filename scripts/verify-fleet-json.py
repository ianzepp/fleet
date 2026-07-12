#!/usr/bin/env python3
"""Validate the shape and cross-references of a fleet.json config.

  verify-fleet-json.py --project <root>
  verify-fleet-json.py --fleet /path/to/fleet.json
  verify-fleet-json.py --project <root> --json
  verify-fleet-json.py --project <root> --strict        # warnings count as errors
  verify-fleet-json.py --project <root> --no-path-checks # skip on-disk path refs

Checks JSON parse, required-for-function keys, cross-reference meaning
(default_hand resolves; mail_identity unique within the mailspace; merges_to_main
only on a hand), executive_cadence / wake-field well-formedness, and that
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
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import ensure_dict, ensure_list, require_python  # noqa: E402

require_python()

HEAD_KEYS = ("head-ceo", "head-cto", "head-cxo")
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
    cad = block.get("executive_cadence")
    if cad is None:
        return
    cwhere = "%s.executive_cadence" % where
    if not isinstance(cad, dict):
        report.err(cwhere, "must be an object")
        return
    en = cad.get("enabled")
    if not isinstance(en, bool):
        report.err("%s.enabled" % cwhere, "must be boolean, got %r" % (en,))
    # every_n_loops (sweep multiplier) is the configurable knob:
    # sweep_interval = every_n_loops × mind_loop.interval_sec.
    enl = cad.get("every_n_loops")
    if enl is not None:
        if not isinstance(enl, int) or isinstance(enl, bool) or enl < 1:
            report.err("%s.every_n_loops" % cwhere, "must be a positive integer, got %r" % (enl,))
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

    # --- default_hand cross-reference (hands may be keyed as 'hunters' in legacy fleets) ---
    hands = ensure_dict(fleet.get("hands") or fleet.get("hunters"))
    if fleet.get("default_hand") is not None:
        dh = fleet.get("default_hand")
        if not isinstance(dh, str) or dh not in hands:
            report.err("$.default_hand", "references missing hand: %r (known: %s)" % (dh, sorted(hands) or "(none)"))

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
        if "merges_to_main" in h and not isinstance(h.get("merges_to_main"), bool):
            report.err(where, "merges_to_main must be boolean, got %r" % (h.get("merges_to_main"),))
        pkt = h.get("packet")
        if pkt is not None and not isinstance(pkt, dict):
            report.warn(where, "packet must be an object or null (unassigned)")
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
        if block.get("merges_to_main") is True:
            report.err(where, "merges_to_main=true on a head — only hands merge to main")
        la = block.get("legacy_aliases")
        if la is not None and not isinstance(la, list):
            report.warn(where, "legacy_aliases should be a list, got %r" % (type(la).__name__,))
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
    ap.add_argument("--project", "-p", default=None, help="Fleet project root (default fleet = PROJECT/.vivi/fleet.json)")
    ap.add_argument("--fleet", "-f", default=None, help="Path to fleet.json (overrides --project)")
    ap.add_argument("--json", action="store_true", help="Machine-readable JSON output instead of text")
    ap.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    ap.add_argument("--no-path-checks", action="store_true", help="Skip on-disk existence checks for referenced paths")
    args = ap.parse_args(argv)

    fleet_path: Optional[Path] = None
    if args.fleet:
        fleet_path = Path(args.fleet).expanduser().resolve()
    elif args.project:
        fleet_path = Path(args.project).expanduser().resolve() / ".vivi" / "fleet.json"
    if not fleet_path:
        ap.error("provide --project or --fleet")
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
    fleet_id = fleet.get("fleet_id") or fleet.get("mailspace") or fleet_path.parent.parent.name

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
