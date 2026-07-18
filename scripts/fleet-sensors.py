#!/usr/bin/env python3
"""Cheap FLEET_CYCLE sensor snapshot for one fleet project.

Emits JSON (default) or a short text summary for Mind fail-fast cycles.

  fleet-sensors.py --project /path/to/fleet [--json|--text]
  fleet-sensors.py --project /path --no-watch --tail 12

Requires: Python 3.9+ (macOS / Linux).
Exit: 0 ok · 1 hard error (missing project/fleet) · 2 sensors partial (still prints JSON)
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    FleetScopeError,
    add_fleet_scope_arguments,
    exact_tmux_session,
    exact_tmux_target,
    load_json as _load_json,
    now_iso,
    require_python,
    resolve_fleet_file,
    run_cmd,
    which,
)

require_python()


def run(cmd: List[str], timeout: float = 30.0) -> tuple:
    return run_cmd(cmd, timeout=timeout)


def load_json(path: Path) -> dict:
    data = _load_json(path, default={})
    return data if isinstance(data, dict) else {}


def _parse_iso(s):
    """Parse an ISO-8601 timestamp to a tz-aware datetime; unparseable/None -> None."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _secs_since(ts_iso, now_dt):
    """Seconds between ts_iso and now_dt, or None if ts_iso is unparseable."""
    t = _parse_iso(ts_iso)
    if t is None:
        return None
    return (now_dt - t).total_seconds()


def head_state_block(baseline: dict, key: str) -> dict:
    """Baseline per-head bookkeeping under documented hyphen keys (legacy underscore ok)."""
    block = baseline.get(key)
    if isinstance(block, dict):
        return block
    alt = key.replace("-", "_")
    block = baseline.get(alt)
    return block if isinstance(block, dict) else {}


def is_vivi_pty_role(slot: dict) -> bool:
    runtime = slot.get("runtime") or {}
    return isinstance(runtime, dict) and runtime.get("kind") == "vivi_pty"


def _model_fields(value: Any) -> Dict[str, Any]:
    """Return only structured model evidence; free-form terminal text is never evidence."""
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in ("agent", "provider", "model", "reasoning"):
        item = value.get(key)
        if isinstance(item, (str, int, float, bool)) and str(item).strip():
            result[key] = item
    return result


def _observed_model(diagnostic: dict) -> Dict[str, Any]:
    """Merge structured runtime evidence; earlier normalized candidates win per field."""
    result = {}
    for candidate in (
        diagnostic.get("model_provenance"),
        (diagnostic.get("runtime") or {}).get("model_provenance") if isinstance(diagnostic.get("runtime"), dict) else None,
        diagnostic.get("runtime"),
        diagnostic.get("session"),
        diagnostic,
    ):
        for key, value in _model_fields(candidate).items():
            result.setdefault(key, value)
    return result


def capture_vivi_pty(session_id: str, socket: str, vivi_pty_bin: str) -> dict:
    """Capture one canonical runtime observation from vivi-pty diagnostics."""
    unavailable = {
        "exists": False,
        "tail": "",
        "state": "unknown",
        "process_state": "unknown",
        "confidence": "low",
        "evidence": [],
        "model": {},
    }
    if not vivi_pty_bin:
        return unavailable
    rc, out = run(
        [vivi_pty_bin, "session", "diagnostic", session_id, "--socket", socket],
        timeout=5,
    )
    if rc != 0:
        return unavailable
    try:
        diagnostic = json.loads(out)
    except Exception:
        return unavailable
    process_state = diagnostic.get("process_state") or (diagnostic.get("session") or {}).get("state", "unknown")
    terminal = diagnostic.get("terminal") or {}
    stopped = process_state in ("exited", "stopped")
    return {
        "exists": not stopped,
        "tail": terminal.get("contents", "") or "",
        "state": "stopped" if stopped else diagnostic.get("harness_state", "unknown"),
        "process_state": process_state,
        "confidence": diagnostic.get("confidence", "low"),
        "evidence": diagnostic.get("evidence") or [],
        "model": _observed_model(diagnostic),
    }


def classify_vivi_pty(state: str, text: str, session_exists: bool) -> str:
    """Map normalized vivi-pty state, falling back to terminal evidence."""
    if not session_exists or state == "stopped":
        return "stopped"
    if state in (
        "starting",
        "waiting_for_input",
        "submitting",
        "running",
        "approval_required",
        "completed",
        "failed",
    ):
        return state
    return classify_terminal(text, session_exists)


def failure_detail(text: str) -> Optional[str]:
    if re.search(r"over capacity|rate limit|[^0-9]429[^0-9]|usage limit hard|try again later", text or "", re.I):
        return "capacity"
    if re.search(
        r"ECONNRESET|connection failed|connection error|connect timed out|request timed out|"
        r"stream timed out|network timeout|TLS handshake timeout|websocket.*timeout",
        text or "",
        re.I,
    ):
        return "connection"
    return "runtime" if text else None


def classify_terminal(text: str, session_exists: bool) -> str:
    """Classify terminal evidence when no normalized runtime state is available."""
    if not session_exists:
        return "stopped"
    t = text or ""
    last_lines = [x for x in (t.splitlines() or []) if x.strip()]
    bottom = "\n".join(last_lines[-6:]) if last_lines else ""
    if re.search(
        r"Working \(|esc to interrupt|Waiting for response|Responding…|Responding\.\.\.|Thinking…"
        r"|[🌑🌒🌓🌔🌕🌖🌗🌘]\s*·\s*Tip:",
        t,
        re.I,
    ):
        return "running"
    if re.search(
        r"Yes, continue|Do you trust|trust this workspace|No, quit|Press enter to continue"
        r"|Always allow|Allow always|Allow once|until OpenCode is restarted"
        r"|Approve once|Approve for this session|Reject with feedback|Write this file\?|↵ confirm",
        t,
        re.I,
    ):
        return "approval_required"
    if re.search(r"over capacity|rate limit|[^0-9]429[^0-9]|usage limit hard|try again later", t, re.I):
        return "failed"
    if re.search(
        r"ECONNRESET|connection failed|connection error|connect timed out|request timed out|"
        r"stream timed out|network timeout|TLS handshake timeout|websocket.*timeout",
        t,
        re.I,
    ):
        return "failed"
    # Codex ready chrome
    if "›" in t:
        if re.search(r"bag empty|standing by|turn end|Turn completed|ready-to-merge", t, re.I):
            return "completed"
        return "waiting_for_input"
    # Grok-style prompt box
    if re.search(r"Grok|always-approve|Shift\+Tab", t) and re.search(r"Turn completed|Idle until|Board empty|bag empty|❯", t, re.I):
        if re.search(r"Turn completed|Idle until|Board empty|bag empty|actionable: 0", t, re.I):
            return "completed"
        return "waiting_for_input"
    if re.search(r"❯\s*$|╰─.*Grok|codex ›|^\s*›\s*$", t, re.M):
        return "waiting_for_input"
    # Kimi Code TUI — boxed composer plus model/context status chrome.
    if last_lines and re.search(r"context:\s*\d+%", last_lines[-1]):
        if re.search(r"│\s*>\s*", bottom):
            return "waiting_for_input"
    # opencode TUI — status bar markers like "OpenCode Zen" / "Build ·" / "ctrl+p commands"
    if re.search(r"OpenCode Zen|Build auto|Build ·|ctrl\+p commands", t):
        bottom = "\n".join(last_lines[-6:]) if last_lines else ""
        if re.search(r"Ask anything\.\.\.", bottom):
            return "waiting_for_input"
        if re.search(r"⬝|esc interrupt", bottom):
            return "running"
        return "waiting_for_input"
    return "unknown"


def parse_status_table(text: str) -> Dict[str, Dict[str, int]]:
    """Parse `vivi mailspace status` identity rows."""
    rows = {}  # type: Dict[str, Dict[str, int]]
    for line in text.splitlines():
        # hand-1    0           0           0           0           0             13
        m = re.match(
            r"^(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$",
            line.strip(),
        )
        if not m:
            continue
        name = m.group(1)
        if name in ("identity", "total"):
            continue
        rows[name] = {
            "actionable": int(m.group(2)),
            "tasks_open": int(m.group(3)),
            "needs_open": int(m.group(4)),
            "wants_open": int(m.group(5)),
            "inbox_unread": int(m.group(6)),
            "done": int(m.group(7)),
        }
    return rows


def list_open_handles(vivi: str, project: str, identity: str, kind: str = "task") -> List[Dict[str, str]]:
    cmd = [vivi, kind, "list", "--for", identity, "--project", project]
    rc, out = run(cmd, timeout=20)
    if rc != 0:
        return []
    handles = []  # type: List[Dict[str, str]]
    for line in out.splitlines():
        # handle  status  role  date  from  subject
        if "open" not in line or line.strip().startswith("handle"):
            continue
        parts = line.split()
        if len(parts) >= 2 and re.match(r"^[a-f0-9]{6,}$", parts[0]):
            # subject is rest after date-ish fields — crude but useful
            subj = ""
            if "  " in line:
                # find subject after last ISO date fragment
                m = re.search(r"\d{4}-\d{2}-\d{2}T\S+\s+\S+\s+(.*)$", line)
                subj = (m.group(1).strip() if m else "").strip()
            handles.append({"handle": parts[0], "status": "open", "subject": subj or line.strip()})
    return handles


def lane_binding(hand: dict) -> Optional[dict]:
    """Return the durable campaign/packet binding that makes a Hand a lane."""
    lane = hand.get("lane")
    if isinstance(lane, dict) and lane:
        return {**lane, "binding_kind": "lane"}
    packet = hand.get("packet")
    if isinstance(packet, dict) and packet:
        return {**packet, "binding_kind": "packet"}
    return None


def lane_progress_signature(
    binding: dict,
    open_tasks: List[Dict[str, str]],
    open_needs: List[Dict[str, str]],
    mail_top_handle: Optional[str],
    git_state: dict,
) -> str:
    """Hash product evidence; runtime chrome is deliberately excluded."""
    payload = {
        "binding": binding,
        "tasks": sorted(x.get("handle") for x in open_tasks if x.get("handle")),
        "needs": sorted(x.get("handle") for x in open_needs if x.get("handle")),
        "mail_top": mail_top_handle,
        "git": git_state,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def lane_git_state(cwd: str, remote: bool = False) -> dict:
    """Read a local lane's Git identity without changing its worktree."""
    if remote:
        return {"available": False, "reason": "remote"}
    path = Path(cwd)
    if not path.is_dir():
        return {"available": False, "reason": "missing_cwd"}
    rc, head = run(["git", "-C", str(path), "rev-parse", "HEAD"], timeout=8)
    if rc != 0:
        return {"available": False, "reason": "not_git"}
    rc, status = run(["git", "-C", str(path), "status", "--porcelain=v1", "--untracked-files=normal"], timeout=12)
    if rc != 0:
        return {"available": False, "reason": "status_failed", "head": head.strip()}
    return {
        "available": True,
        "head": head.strip(),
        "dirty": bool(status),
        "status_hash": hashlib.sha256(status.encode("utf-8")).hexdigest()[:20],
    }


def lane_progress_observation(
    previous: dict,
    signature: str,
    now: datetime,
    stale_after_cycles: int,
    resume_stale_after_hours: int,
    runtime_state: str,
    has_open_work: bool,
    intentionally_parked: bool,
) -> dict:
    """Classify a bound lane for Mind review; never authorize teardown."""
    same = previous.get("signature") == signature
    unchanged_cycles = int(previous.get("unchanged_cycles") or 0) + 1 if same else 0
    last_progress_at = previous.get("last_progress_at") if same else now.isoformat()
    resume_stale = False
    if same and last_progress_at and resume_stale_after_hours > 0:
        then = _parse_iso(last_progress_at)
        if then is not None:
            resume_stale = (now - then.astimezone(timezone.utc)).total_seconds() >= resume_stale_after_hours * 3600
    idle = runtime_state in ("waiting_for_input", "completed", "stopped", "unknown")
    candidate = idle and not intentionally_parked and (
        unchanged_cycles >= stale_after_cycles or resume_stale
    )
    reason = None
    if candidate:
        reason = "resume_stale" if resume_stale else ("stale_bound" if has_open_work else "empty_retained")
    return {
        "signature": signature,
        "unchanged_cycles": unchanged_cycles,
        "last_progress_at": last_progress_at,
        "candidate": candidate,
        "reason": reason,
        "runtime_idle": idle,
        "intentionally_parked": intentionally_parked,
    }


def _parse_mail_line(line):
    """Parse one `vivi mail list` row into (handle, date, from, subject) or None.

    Format is version-dependent: `handle [iso-date] from subject…` — the date
    column may be absent. Leading whitespace is ignored; handle must be hex.
    """
    line = line.strip()
    if not line or line.startswith("handle"):
        return None
    parts = line.split(None, 3)
    if len(parts) < 3 or not re.match(r"^[a-f0-9]{6,}$", parts[0]):
        return None
    if len(parts) >= 4 and re.match(r"^\d{4}-\d{2}-\d{2}T", parts[1]):
        return parts[0], parts[1], parts[2], parts[3].strip()
    return parts[0], None, parts[1], (parts[2].strip() if len(parts) > 2 else "")


def list_mail_from_operator(
    vivi: str, project: str, mind_identity: str, operator_identity: str, limit: int = 20
) -> List[Dict[str, str]]:
    """Cheap scan of mind@ for mail FROM operator@ (operator feedback / decisions)."""
    if not vivi:
        return []
    cmd = [vivi, "mail", "list", "--for", mind_identity, "--project", project]
    rc, out = run(cmd, timeout=20)
    if rc != 0 or not out.strip():
        return []
    op_token = (operator_identity or "operator").lower()
    found = []  # type: List[Dict[str, str]]
    for line in out.splitlines():
        parsed = _parse_mail_line(line)
        if parsed is None:
            continue
        handle, date, frm, subj = parsed
        fl = frm.lower()
        if op_token not in fl and not fl.startswith("operator@"):
            continue
        found.append({"handle": handle, "from": frm, "subject": subj, "date": date})
        if len(found) >= limit:
            break
    return found


def list_mail_from_identity(vivi, project, recipient, sender_tokens, limit=5):
    """Newest-first mail in `recipient`'s inbox FROM any of `sender_tokens`.

    Detects executive-head sweep completion: a head "completed" a sweep when a
    mail appears in the report inbox (default mind) from that head's mail
    identity or a configured legacy_aliases entry (e.g. strategist/correctness/
    purity). Cheap line scan of `vivi mail list`; returns
    [{handle, from, subject, date}], newest first (mail list is newest-first).
    """
    if not vivi or not recipient:
        return []
    cmd = [vivi, "mail", "list", "--for", recipient, "--project", project]
    rc, out = run(cmd, timeout=20)
    if rc != 0 or not out.strip():
        return []
    tokens = [str(t).lower() for t in sender_tokens if t]
    found = []
    for line in out.splitlines():
        parsed = _parse_mail_line(line)
        if parsed is None:
            continue
        handle, date, frm, subj = parsed
        fl = frm.lower()
        if not any(tok and tok in fl for tok in tokens):
            continue
        found.append({"handle": handle, "from": frm, "subject": subj, "date": date})
        if len(found) >= limit:
            break
    return found


def list_ready_to_merge(vivi, project, recipient, limit=30):
    """Newest RTM mail sent to Mind, cheap enough for every sensor cycle."""
    if not vivi or not recipient:
        return []
    rc, out = run([vivi, "mail", "list", "--for", recipient, "--project", project], timeout=20)
    if rc != 0 or not out.strip():
        return []
    found = []
    for line in out.splitlines():
        parsed = _parse_mail_line(line)
        if parsed is None:
            continue
        handle, date, frm, subj = parsed
        if not re.search(r"\bready[- ]to[- ]merge\b", subj, re.I):
            continue
        commits = re.findall(r"(?<![0-9a-f])[0-9a-f]{7,40}(?![0-9a-f])", subj, re.I)
        found.append(
            {
                "handle": handle,
                "from": frm,
                "subject": subj,
                "date": date,
                "commit": commits[-1] if commits else None,
            }
        )
        if len(found) >= limit:
            break
    return found


def list_recent_mail(vivi, project, recipient, limit=100):
    """Newest mail metadata for cheap subject-level reconciliation."""
    if not vivi or not recipient:
        return []
    rc, out = run([vivi, "mail", "list", "--for", recipient, "--project", project], timeout=20)
    if rc != 0 or not out.strip():
        return []
    found = []
    for line in out.splitlines():
        parsed = _parse_mail_line(line)
        if parsed is None:
            continue
        handle, date, frm, subj = parsed
        found.append({"handle": handle, "from": frm, "subject": subj, "date": date})
        if len(found) >= limit:
            break
    return found


def list_memos(vivi, project, identity, limit=20):
    """Newest role memos for cold-boot checklist context.

    Memos are intentionally subject-first line items. Sensors list metadata only;
    Mind can `vivi memo show <handle>` when a body is needed.
    """
    if not vivi or not identity or limit <= 0:
        return []
    rc, out = run([vivi, "memo", "list", "--for", identity, "--project", project], timeout=20)
    if rc != 0 or not out.strip():
        return []
    found = []
    for line in out.splitlines():
        parsed = _parse_memo_line(line)
        if parsed is None:
            continue
        handle, date, subj = parsed
        found.append({"handle": handle, "date": date, "subject": subj})
        if len(found) >= limit:
            break
    return found


def _parse_memo_line(line):
    """Parse one `vivi memo list` row into (handle, date, subject) or None."""
    line = line.strip()
    if not line or line.startswith("handle"):
        return None
    parts = line.split(None, 2)
    if len(parts) < 2 or not re.match(r"^[a-f0-9]{6,}$", parts[0]):
        return None
    if len(parts) >= 3 and re.match(r"^\d{4}-\d{2}-\d{2}T", parts[1]):
        return parts[0], parts[1], parts[2].strip()
    return parts[0], None, (parts[1].strip() if len(parts) > 1 else "")


def rtm_completion_mail(rtm: dict, recent_mail: list, main_identity: str) -> Optional[dict]:
    """Find a newer main-Hand merge completion with strong subject overlap."""
    stop = {"ready", "merge", "merged", "packet", "pass", "done", "first", "playability", "re"}
    words = {
        w
        for w in re.findall(r"[a-z0-9]+", (rtm.get("subject") or "").lower())
        if len(w) >= 3 and w not in stop and not re.fullmatch(r"[0-9a-f]{7,40}", w)
    }
    rtm_date = _parse_iso(rtm.get("date"))
    main_token = (main_identity or "hand-1").lower()
    for mail in recent_mail:
        if main_token not in (mail.get("from") or "").lower():
            continue
        subject = (mail.get("subject") or "").lower()
        if "merge" not in subject or "done" not in subject:
            continue
        mail_date = _parse_iso(mail.get("date"))
        if rtm_date and mail_date and mail_date < rtm_date:
            continue
        overlap = words.intersection(re.findall(r"[a-z0-9]+", subject))
        if len(overlap) >= 2 or any(len(word) >= 5 for word in overlap):
            return mail
    return None


def git_root(cwd: Path) -> Optional[Path]:
    """Walk parents for .git (file or dir) — workspace containers often lack root git."""
    cur = cwd.resolve() if cwd.is_dir() else cwd.parent
    for _ in range(12):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def git_tip(cwd: Path, fleet: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Tip for a product checkout. Walks parents; container fleets may set git.main_cwd
    or rely on a single-level child .git scan when project root is not a repo."""
    candidates = []  # type: List[Path]
    if cwd:
        candidates.append(Path(cwd))
    if fleet:
        gcfg = fleet.get("git") if isinstance(fleet.get("git"), dict) else {}
        for key in ("main_cwd", "primary"):
            p = gcfg.get(key)
            if p:
                candidates.append(Path(p))
        # one-level children of fleet project (workspace container)
        proj = fleet.get("project")
        if proj:
            pp = Path(proj)
            if pp.is_dir():
                try:
                    for child in sorted(pp.iterdir()):
                        if child.is_dir() and not child.name.startswith(".") and (child / ".git").exists():
                            candidates.append(child)
                except OSError:
                    pass
    seen = set()  # type: set
    last_err = {"cwd": str(cwd), "error": "not a git dir"}
    for cand in candidates:
        key = str(cand)
        if key in seen:
            continue
        seen.add(key)
        root = git_root(cand) if cand else None
        if root is None:
            continue
        tip = _git_tip_at(root)
        if tip.get("sha"):
            return tip
        last_err = tip
    return last_err


def _git_tip_at(cwd: Path) -> Dict[str, Any]:
    rc, out = run(["git", "-C", str(cwd), "log", "-1", "--format=%H %s"], timeout=10)
    if rc != 0:
        return {"cwd": str(cwd), "error": out.strip()[:200]}
    parts = out.strip().split(" ", 1)
    sha = parts[0][:12] if parts else ""
    subj = parts[1] if len(parts) > 1 else ""
    rc2, st = run(["git", "-C", str(cwd), "status", "-sb"], timeout=10)
    dirty = False
    ahead = None  # type: Optional[int]
    behind = None  # type: Optional[int]
    dirty_paths = []  # type: List[str]
    if rc2 == 0:
        first = st.splitlines()[0] if st.strip() else ""
        status_lines = [ln for ln in st.splitlines() if ln.strip() and not ln.startswith("##")]
        dirty = bool(status_lines)
        dirty_paths = [ln[3:].strip() if len(ln) > 3 else ln.strip() for ln in status_lines[:8]]
        m = re.search(r"ahead (\d+)", first)
        if m:
            ahead = int(m.group(1))
        m = re.search(r"behind (\d+)", first)
        if m:
            behind = int(m.group(1))
    return {
        "cwd": str(cwd),
        "sha": sha,
        "subject": subj,
        "dirty": dirty,
        "status_sb": st.strip().splitlines()[0] if st.strip() else "",
        "ahead": ahead,
        "behind": behind,
        "dirty_paths": dirty_paths,
    }


def commit_is_on_main(main_cwd: Optional[str], commit: Optional[str]) -> Optional[bool]:
    """Return whether commit is an ancestor of main; None when it cannot be checked."""
    if not main_cwd or not commit:
        return None
    rc, _ = run(["git", "-C", main_cwd, "cat-file", "-e", "%s^{commit}" % commit], timeout=5)
    if rc != 0:
        return None
    rc, _ = run(["git", "-C", main_cwd, "merge-base", "--is-ancestor", commit, "HEAD"], timeout=5)
    return rc == 0



def resolve_tmux_bin(tooling: Optional[Dict[str, Any]] = None) -> str:
    """Resolve tmux binary from tooling override, PATH, then common install paths."""
    found = which("tmux", tooling, "tmux") if tooling else which("tmux")
    if not found:
        found = which("tmux")
    if found:
        return found
    for cand in (
        "/opt/homebrew/bin/tmux",
        "/usr/local/bin/tmux",
        "/usr/bin/tmux",
        "/home/linuxbrew/.linuxbrew/bin/tmux",
    ):
        if Path(cand).is_file():
            return cand
    return "tmux"


# Mind loop base tick (seconds). Head cadence = every_n_loops × this.
# Override the base tick via fleet.json mind_loop.interval_sec (or loop_interval_sec).
MIND_LOOP_DEFAULT_SEC = 300

# Default every_n_loops (Head sweep multiplier) by posture × role when the head
# does not set executive_cadence.every_n_loops. 0 = on-call (no schedule).
# N >= 1 = scheduled: due every N × mind_loop.interval_sec. Dormant pauses all.
HEAD_CADENCE_DEFAULTS = {
    "growth": {"head-cto": 6, "head-cxo": 12, "head-ceo": 36},   # @5m: 30m / 1h / 3h
    "standby": {"head-cto": 18, "head-cxo": 36, "head-ceo": 72},  # @5m: 1.5h / 3h / 6h
    # dormant: no table — sweeps paused; heads without a default stay on-call (0)
}

DR_TIER_DEFAULTS = {
    "inventory": {"freshness_check_days": 30, "analysis_days": 90, "restore_drill_days": None},
    "critical": {"freshness_check_days": 14, "analysis_days": 60, "restore_drill_days": 180},
    "regulated_or_irreplaceable": {"freshness_check_days": 7, "analysis_days": 30, "restore_drill_days": 90},
}
DR_DEFAULT_GRACE_DAYS = 7
DR_RECEIPT_KEYS = (
    "last_report_handle",
    "last_report_at",
    "last_status",
    "last_coverage",
    "last_rpo",
    "last_rto",
    "last_restore_evidence",
)


def mind_loop_interval_sec(fleet: dict) -> int:
    """Base FLEET_CYCLE / Mind loop tick in seconds (default 300 = 5m)."""
    ml = fleet.get("mind_loop") if isinstance(fleet.get("mind_loop"), dict) else {}
    raw = ml.get("interval_sec")
    if raw is None:
        raw = fleet.get("loop_interval_sec")
    try:
        sec = int(raw) if raw is not None else MIND_LOOP_DEFAULT_SEC
    except (TypeError, ValueError):
        sec = MIND_LOOP_DEFAULT_SEC
    if sec <= 0:
        sec = MIND_LOOP_DEFAULT_SEC
    return sec


def head_cadence_default_every_n_loops(posture_mode: str, head_key: str) -> int:
    """Posture×role default multiplier. 0 if no schedule for this head/posture."""
    table = HEAD_CADENCE_DEFAULTS.get(posture_mode)
    if not isinstance(table, dict):
        return 0
    n = table.get(head_key)
    if n is None:
        return 0
    try:
        return max(0, int(n))
    except (TypeError, ValueError):
        return 0


def resolve_head_every_n_loops(
    posture_mode: str,
    head_key: str,
    cad: Any = None,
) -> int:
    """Resolve Head schedule multiplier (every_n_loops).

    Single dial for Head scheduling:

    - **0** — on-call: no ``head_due_*``; only explicit Mind tasks wake the Head
    - **N >= 1** — scheduled: Mind should wake a sweep every N × mind_loop ticks

    Resolution order:

    1. Explicit ``executive_cadence.every_n_loops`` (including 0) wins.
    2. Legacy ``enabled: false`` without every_n_loops → 0 (on-call).
    3. Legacy ``enabled: true`` without every_n_loops → posture×role default
       (or 0 if that head has no default).
    4. No cadence block → posture×role default (or 0).

    ``self_directed`` is ignored (removed as a peer knob).
    """
    if not isinstance(cad, dict):
        cad = {}
    raw = cad.get("every_n_loops")
    if raw is not None:
        try:
            n = int(raw)
        except (TypeError, ValueError):
            n = 0
        return max(0, n)
    # Legacy enable flag only when every_n_loops omitted
    if cad.get("enabled") is False:
        return 0
    if cad.get("enabled") is True:
        # Legacy: schedule on using posture×role default (or 0 if no default)
        return head_cadence_default_every_n_loops(posture_mode, head_key)
    # No cadence block, empty block, or enabled omitted → on-call (0).
    # To schedule: set every_n_loops >= 1 (or legacy enabled: true).
    return 0


def head_cadence_every_n_loops(posture_mode: str, head_key: str, override: Any = None) -> int:
    """Compatibility wrapper: override alone, or posture default.

    Prefer :func:`resolve_head_every_n_loops` when a cadence block is available.
    """
    if override is not None:
        try:
            return max(0, int(override))
        except (TypeError, ValueError):
            return 0
    return head_cadence_default_every_n_loops(posture_mode, head_key)


def head_sweep_interval_sec(
    fleet: dict,
    posture_mode: str,
    head_key: str,
    every_n: Any = None,
) -> int:
    """Seconds between Head sweeps: every_n_loops × mind_loop.interval_sec.

    When every_n is 0 (on-call), returns a large sentinel interval; callers should
    treat every_n == 0 as not due rather than relying on this alone.
    """
    loop = mind_loop_interval_sec(fleet)
    try:
        n = int(every_n) if every_n is not None else head_cadence_default_every_n_loops(
            posture_mode, head_key
        )
    except (TypeError, ValueError):
        n = 0
    n = max(0, n)
    if n <= 0:
        return loop  # unused when on-call; keep positive for arithmetic
    return max(n * loop, loop)


def resolve_posture(fleet: dict, baseline: dict) -> tuple:
    """Return (mode, suppress_starvation, pause_executive_sweeps, posture_out_dict).

    Hands: standby+dormant suppress starvation refill (quiet Hands is success).
    Heads: only dormant pauses default executive cadence; standby allows
    stewardship sweeps (not expansion). Cadence spacing = every_n_loops ×
    mind_loop.interval_sec when every_n_loops >= 1; every_n_loops 0 = on-call.
    See fleet-posture.md.
    """
    posture_block = fleet.get("fleet_posture") if isinstance(fleet.get("fleet_posture"), dict) else {}
    if not posture_block and isinstance(baseline.get("fleet_posture"), dict):
        posture_block = baseline.get("fleet_posture") or {}
    mode = str(posture_block.get("mode") or "growth").lower()
    if mode in ("campaign", "active"):
        mode = "growth"
    if mode in ("on_call", "on-call"):
        mode = "standby"
    suppress_starvation = mode in ("standby", "dormant")
    pause_executive_sweeps = mode == "dormant"
    default_sweep = {
        "growth": "expansion",
        "standby": "stewardship",
        "dormant": "paused",
    }.get(mode, "expansion")
    loop_sec = mind_loop_interval_sec(fleet)
    return (
        mode,
        suppress_starvation,
        pause_executive_sweeps,
        {
            "mode": mode,
            "reason": posture_block.get("reason"),
            "default_head_sweep_mode": default_sweep,
            "mind_loop_interval_sec": loop_sec,
        },
    )


def _strict_positive_int(value: Any, field: str, allow_null: bool = False) -> Optional[int]:
    if value is None and allow_null:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s must be a positive integer" % field)
    if value <= 0:
        raise ValueError("%s must be a positive integer" % field)
    return value


def disaster_recovery_policy(fleet: dict) -> Optional[dict]:
    raw = fleet.get("disaster_recovery")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("disaster_recovery must be an object")
    enabled_raw = raw.get("enabled", False)
    if not isinstance(enabled_raw, bool):
        raise ValueError("disaster_recovery.enabled must be boolean")
    if not enabled_raw:
        return None
    if "tier" not in raw:
        raise ValueError("disaster_recovery.tier is required when enabled")
    tier_raw = raw.get("tier")
    if not isinstance(tier_raw, str):
        raise ValueError("disaster_recovery.tier must be a string")
    tier = tier_raw
    if tier == "off":
        return None
    if tier not in DR_TIER_DEFAULTS:
        raise ValueError("disaster_recovery.tier must be off, inventory, critical, or regulated_or_irreplaceable")
    defaults = DR_TIER_DEFAULTS[tier]
    policy = {"enabled": True, "tier": tier}
    for field in ("freshness_check_days", "analysis_days"):
        policy[field] = _strict_positive_int(raw.get(field, defaults[field]), field)
    restore_raw = raw.get("restore_drill_days", defaults["restore_drill_days"])
    policy["restore_drill_days"] = _strict_positive_int(restore_raw, "restore_drill_days", allow_null=True)
    policy["grace_days"] = _strict_positive_int(raw.get("grace_days", DR_DEFAULT_GRACE_DAYS), "grace_days")
    return policy


def _dr_receipts(baseline: dict) -> dict:
    raw = baseline.get("disaster_recovery")
    return raw if isinstance(raw, dict) else {}


def _receipt_date(receipts: dict, field: str, errors: List[str]) -> Optional[datetime]:
    value = receipts.get(field)
    if value in (None, ""):
        return None
    parsed = _parse_iso(value)
    if parsed is None:
        errors.append("invalid %s" % field)
    return parsed


def _whole_days_since(moment: datetime, now_dt: datetime) -> int:
    return max(0, int((now_dt - moment).total_seconds() // 86400))


def _dr_due_state(last_at: Optional[datetime], cadence_days: Optional[int], grace_days: int, now_dt: datetime) -> dict:
    if cadence_days is None:
        return {"applicable": False, "due": False, "overdue": False, "days_since": None, "days_overdue": None}
    if last_at is None:
        return {"applicable": True, "due": True, "overdue": False, "days_since": None, "days_overdue": None}
    days_since = _whole_days_since(last_at, now_dt)
    days_overdue = max(0, days_since - cadence_days)
    return {
        "applicable": True,
        "due": days_since > cadence_days,
        "overdue": days_overdue > grace_days,
        "days_since": days_since,
        "days_overdue": days_overdue,
    }


def evaluate_disaster_recovery(
    fleet: dict,
    baseline: dict,
    posture_mode: str,
    now_dt: datetime,
    coo_open_tasks: Optional[List[Dict[str, str]]] = None,
) -> tuple:
    """Return (state, signals) for opt-in COO disaster-recovery stewardship."""
    try:
        policy = disaster_recovery_policy(fleet)
    except ValueError as exc:
        return {"enabled": True, "status": "unknown", "error": str(exc)}, ["head_due_coo_dr_analysis"]
    if policy is None:
        return None, []

    receipts = _dr_receipts(baseline)
    errors = []  # type: List[str]
    freshness_at = _receipt_date(receipts, "last_freshness_check_at", errors)
    analysis_at = _receipt_date(receipts, "last_analysis_at", errors)
    restore_at = _receipt_date(receipts, "last_restore_drill_at", errors)
    receipt_pairs = [
        ("last_freshness_check_at", freshness_at),
        ("last_analysis_at", analysis_at),
        ("last_restore_drill_at", restore_at),
    ]
    future_fields = {field for field, value in receipt_pairs if value is not None and value > now_dt}
    if future_fields:
        errors.extend("future %s" % field for field in sorted(future_fields))
        if "last_freshness_check_at" in future_fields:
            freshness_at = None
        if "last_analysis_at" in future_fields:
            analysis_at = None
        if "last_restore_drill_at" in future_fields:
            restore_at = None
    any_valid_receipt = bool(freshness_at or analysis_at or restore_at)

    due = {
        "freshness": _dr_due_state(freshness_at, policy["freshness_check_days"], policy["grace_days"], now_dt),
        "analysis": _dr_due_state(analysis_at, policy["analysis_days"], policy["grace_days"], now_dt),
        "restore_drill": _dr_due_state(restore_at, policy["restore_drill_days"], policy["grace_days"], now_dt),
    }
    if not any_valid_receipt:
        due["freshness"].update({"due": False, "overdue": False, "days_since": None, "days_overdue": None})
        due["analysis"].update({"due": True, "overdue": False, "days_since": None, "days_overdue": None})
        due["restore_drill"].update({"due": False, "overdue": False, "days_since": None, "days_overdue": None})
    if errors:
        due["analysis"].update({"due": True, "overdue": False, "unknown": True})

    open_tasks = coo_open_tasks or []
    dr_tasks = [task for task in open_tasks if re.search(r"\b(dr|disaster[- ]recovery|recoverability)\b", task.get("subject") or "", re.I)]
    obligation_paused = posture_mode == "dormant" and policy["tier"] in ("critical", "regulated_or_irreplaceable")
    assignment = {
        "outstanding": bool(dr_tasks),
        "outstanding_handles": [task.get("handle") for task in dr_tasks if task.get("handle")],
        "duplicate_suppressed": bool(dr_tasks),
        "paused_by_posture": obligation_paused,
        "action": "suppress_duplicate_existing_assignment" if dr_tasks else "none",
    }
    receipt_state = {
        "last_freshness_check_at": receipts.get("last_freshness_check_at"),
        "last_analysis_at": receipts.get("last_analysis_at"),
        "last_restore_drill_at": receipts.get("last_restore_drill_at"),
        "restore_tested": bool(restore_at),
    }
    for key in DR_RECEIPT_KEYS:
        if key in receipts and isinstance(receipts.get(key), (str, int, float, bool)):
            receipt_state[key] = receipts.get(key)

    signals = []
    for key, signal in (
        ("freshness", "head_due_coo_dr_freshness"),
        ("analysis", "head_due_coo_dr_analysis"),
        ("restore_drill", "head_due_coo_dr_restore_drill"),
    ):
        if due[key].get("due"):
            signals.append(signal)
        if due[key].get("overdue"):
            signals.append(signal.replace("head_due", "head_overdue"))
    if errors:
        signals.append("coo_dr_receipt_unknown")

    return {
        "enabled": True,
        "status": "unknown" if errors else "ok",
        "policy": policy,
        "receipts": receipt_state,
        "due": due,
        "assignment": assignment,
        "errors": errors,
        "false_assurance_bans": ["policy_is_not_evidence", "remote_is_not_restore_proof", "backup_job_is_not_restore_proof"],
    }, signals


def hand_is_paused(baseline: dict, name: str) -> bool:
    pauses = baseline.get("operational_pauses") or []
    if not isinstance(pauses, list):
        return False
    for pause in pauses:
        if isinstance(pause, dict) and pause.get("hand") == name:
            return True
    return False


def head_is_paused(baseline: dict, key: str) -> bool:
    pauses = baseline.get("operational_pauses") or []
    if not isinstance(pauses, list):
        return False
    for pause in pauses:
        if isinstance(pause, dict) and (pause.get("hand") == key or pause.get("head") == key):
            return True
    return False



def build_fingerprint(out: dict, fleet: dict) -> dict:
    """Quiet-compare fingerprint (no durable head report fields)."""
    hands = out.get("hands") or {}
    h1 = hands.get(fleet.get("default_hand") or "hand-1") or next(iter(hands.values()), {})
    h2 = hands.get("hand-2") or {}
    git_main = (out.get("git") or {}).get("main") or {}
    fp = {
        "hand1_open": (h1 or {}).get("actionable") or (h1 or {}).get("tasks_open") or 0,
        "hand2_open": (h2 or {}).get("actionable") or (h2 or {}).get("tasks_open") or 0,
        "next_handle_h1": (h1 or {}).get("next_handle"),
        "next_handle_h2": (h2 or {}).get("next_handle"),
        "swarm_head": (git_main.get("sha") or "")[:12] or None,
        "hand1_state": ((h1 or {}).get("runtime") or {}).get("state"),
        "hand2_state": ((h2 or {}).get("runtime") or {}).get("state"),
        "operator_open": (out.get("operator") or {}).get("open_count", 0),
        "steward_armed": (out.get("steward") or {}).get("armed"),
        "steward_tripped": (out.get("steward") or {}).get("tripped"),
        "map_focus": (fleet.get("focus") or {}).get("chapter")
        or (fleet.get("focus") or {}).get("primary_goal"),
    }
    for hkey, hdata in (out.get("heads") or {}).items():
        sk = hkey.replace("-", "_")
        fp["%s_due" % sk] = hdata.get("sweep_due")
        fp["%s_mail_top" % sk] = hdata.get("mail_top_handle")
        fp["%s_mail_pending" % sk] = hdata.get("mail_pending_handle")
    for hkey, hdata in (out.get("hands") or {}).items():
        sk = hkey.replace("-", "_")
        fp["%s_mail_top" % sk] = hdata.get("mail_top_handle")
        fp["%s_mail_pending" % sk] = hdata.get("mail_pending_handle")
    for stale in list(fp.keys()):
        if re.match(r"^head_(ceo|cto|cxo)_last_(handle|completed)$", stale):
            del fp[stale]
    return fp


def is_product_hand(name: str) -> bool:
    """Implementer Hands only — auditors are review capacity, not product starvation."""
    n = str(name or "")
    return bool(n) and not n.startswith("auditor")


def quiet_hint_from(fp: dict, prev: dict, signals: list, steward: dict) -> bool:
    keys = (
        "hand1_open",
        "hand2_open",
        "next_handle_h1",
        "next_handle_h2",
        "swarm_head",
        "hand1_state",
        "hand2_state",
        "operator_open",
        "steward_tripped",
        "head_ceo_due",
        "head_cto_due",
        "head_cxo_due",
    )
    # Soft: empty-bag starvation + growth refill are obligations, but fingerprint-stable
    # empty fleets must still be allowed to quiet/backoff (disposition lives on refill_hint).
    soft_prefixes = (
        "starvation_candidate_",
        "growth_refill_required",
        "mail_wake_candidate_",  # often stale pending mail on empty bags
    )
    hard = [
        s
        for s in signals
        if not any(str(s).startswith(p) or str(s) == p.rstrip("_") for p in soft_prefixes)
    ]
    # growth_refill_required is exact match (no trailing _); treat as soft for quiet_hint
    hard = [s for s in hard if str(s) != "growth_refill_required"]
    fp_cmp = {k: fp.get(k) for k in keys}
    prev_cmp = {k: prev.get(k) for k in keys}
    return fp_cmp == prev_cmp and not hard and not steward.get("tripped")


def hand_bag_counts(out: dict) -> dict:
    """Count product/open/idle Hand bags from sensors hand rows."""
    hands = out.get("hands") or {}
    open_bags = 0
    idle_open = 0
    running_open = 0
    empty_idle = 0
    product_hands = 0
    product_open = 0
    product_empty_idle = 0
    for name, h in hands.items() if isinstance(hands, dict) else []:
        if not isinstance(h, dict):
            continue
        act = int(h.get("actionable") or h.get("tasks_open") or 0)
        state = str((h.get("runtime") or {}).get("state") or h.get("state") or "")
        proc = str((h.get("runtime") or {}).get("process_state") or "")
        idle = state in ("waiting_for_input", "completed", "stopped", "unknown") or proc == "stopped"
        if act > 0:
            open_bags += 1
            if idle:
                idle_open += 1
            else:
                running_open += 1
        elif idle:
            empty_idle += 1
        if is_product_hand(name):
            product_hands += 1
            if act > 0:
                product_open += 1
            elif idle:
                product_empty_idle += 1
    return {
        "open_bags": open_bags,
        "idle_open": idle_open,
        "running_open": running_open,
        "empty_idle": empty_idle,
        "product_hands": product_hands,
        "product_open": product_open,
        "product_empty_idle": product_empty_idle,
    }


def refill_hint_from(out: dict, signals: list, posture_suppresses_starvation: bool) -> Optional[dict]:
    """When growth product Hands are empty, tell Mind the disposition is Head lower — not quiet/speed.

    Sensors cannot know map truth; they name the required *path*:
    file Head lower (horizon) / executive refill, never invent implement, never quiet-as-ok.
    """
    del signals  # reserved for future map/lower-task probes
    posture = ((out.get("fleet_posture") or {}) if isinstance(out.get("fleet_posture"), dict) else {}).get(
        "mode"
    ) or "growth"
    if posture != "growth" or posture_suppresses_starvation:
        return None
    counts = hand_bag_counts(out)
    if counts["product_hands"] <= 0:
        return None
    # Any open product implement bag → not a refill-empty condition.
    if counts["product_open"] > 0:
        return None
    return {
        "disposition": "file_head_lower",
        "signal": "growth_refill_required",
        "forbidden": [
            "invent_implement",
            "quiet_as_ok",
            "shorten_for_empty_bags",
            "raw_goal_to_hand",
        ],
        "required": [
            "if_map_has_unlowered_unit→assign_head_lower_horizon_3_to_5",
            "if_map_truly_empty_after_executive_sweep→sleep_or_standby",
            "parcel_hand_only_from_citable_delivery_unit",
        ],
        "reason": (
            "growth + product Hand bags empty — not a quiet cycle and not a go-faster signal; "
            "Mind must executive-refill via Head lower (batch-ahead horizon) when map has work, "
            "never invent Hand implement units"
        ),
        "counts": {
            "product_hands": counts["product_hands"],
            "product_open": counts["product_open"],
            "product_empty_idle": counts["product_empty_idle"],
            "open_bags": counts["open_bags"],
        },
    }


def cadence_hint_from(
    out: dict,
    baseline: dict,
    quiet_hint: bool,
    signals: list,
) -> dict:
    """Recommend Mind-loop interval from board/runtime signals already collected.

    Portable temporary supervision until a true Fleet host owns wake/refill.
    Mind applies by replacing the harness scheduler; sensors only advise.
    Ladder (seconds): 180, 300, 600, 900, 1200, 3600. Floor 180 (3m).

    Empty product bags in growth are a *refill disposition* (see refill_hint), not
    a reason to shorten. Shorten only for open bag work, real runtime repair, or
    fresh operator pressure — not board noise + starvation on empty Hands.
    """
    ladder = (180, 300, 600, 900, 1200, 3600)
    # Source of truth for *current* tick: fleet.json via sensors (fleet_posture /
    # per-head mind_loop_interval_sec). Baseline mind_loop is cycle metadata, not
    # the interval. Fall back to temporary 5m base only when fleet omits it.
    configured = None
    posture = out.get("fleet_posture") if isinstance(out.get("fleet_posture"), dict) else {}
    if isinstance(posture.get("mind_loop_interval_sec"), int) and posture["mind_loop_interval_sec"] > 0:
        configured = int(posture["mind_loop_interval_sec"])
    if configured is None:
        heads = out.get("heads") if isinstance(out.get("heads"), dict) else {}
        for _hk, hb in heads.items():
            if isinstance(hb, dict) and isinstance(hb.get("mind_loop_interval_sec"), int) and hb["mind_loop_interval_sec"] > 0:
                configured = int(hb["mind_loop_interval_sec"])
                break
    if configured is None and isinstance(baseline, dict):
        bl = baseline.get("mind_loop") if isinstance(baseline.get("mind_loop"), dict) else {}
        raw = bl.get("interval_sec")
        if isinstance(raw, int) and raw > 0:
            configured = raw
    if configured is None or configured <= 0:
        configured = 300  # temporary base: 5m
    # snap configured to ladder for "current" display
    current = min(ladder, key=lambda x: abs(x - int(configured)))

    sigs = list(signals or [])
    starve = sum(1 for s in sigs if str(s).startswith("starvation_candidate_"))
    wake = sum(1 for s in sigs if "wake_candidate" in str(s))
    # mail_wake on empty bags is not implement demand — ignore for shorten pressure
    mail_wake = sum(1 for s in sigs if str(s).startswith("mail_wake_candidate_"))
    runtime_bad = sum(
        1
        for s in sigs
        if str(s).startswith("runtime_")
        and any(x in str(s) for x in ("_stopped", "_failed", "approval_required"))
    )
    board = "board_event" in sigs
    head_due = any(str(s).startswith("head_due") for s in sigs)
    operator = "operator_to_mind" in sigs or "operator_mail" in sigs
    operator_open = int(((out.get("operator") or {}) if isinstance(out.get("operator"), dict) else {}).get("open_count") or 0)
    growth_refill = "growth_refill_required" in sigs or bool(out.get("refill_hint"))

    counts = hand_bag_counts(out)
    open_bags = counts["open_bags"]
    idle_open = counts["idle_open"]
    running_open = counts["running_open"]
    empty_idle = counts["empty_idle"]

    quiet_streak = 0
    if isinstance(baseline, dict):
        try:
            quiet_streak = int(baseline.get("quiet_streak") or 0)
        except (TypeError, ValueError):
            quiet_streak = 0

    posture_mode = ((out.get("fleet_posture") or {}) if isinstance(out.get("fleet_posture"), dict) else {}).get(
        "mode"
    ) or "growth"

    reasons = []
    target = current

    # Demand: open bag work waiting, runtime repair, real operator needs — NOT empty Hands.
    if idle_open > 0:
        target = min(target, 300)
        reasons.append("idle_open_bag→≤5m")
    if open_bags > 0 and wake >= 2:
        target = min(target, 300)
        reasons.append("open_bag_multi_wake→≤5m")
    if runtime_bad > 0:
        target = min(target, 300)
        reasons.append("runtime_bad→≤5m")
    if operator_open > 0 or (operator and operator_open > 0):
        target = min(target, 300)
        reasons.append("operator_open→≤5m")
    # Fresh operator→mind still worth a tighter tick once; empty absorbed spam should not pin 3m forever.
    # Prefer open needs; if only to_mind signal with open_count 0, hold base (do not shorten below current).
    if board and idle_open > 0:
        target = min(target, 180)
        reasons.append("board+idle_open_bag→3m")
    if head_due and open_bags > 0:
        target = min(target, 300)
        reasons.append("head_due_with_open_bag→≤5m")

    # Empty growth product capacity: disposition is file_head_lower (refill_hint), not go-faster.
    if growth_refill or (posture_mode == "growth" and open_bags == 0 and counts["product_open"] == 0 and empty_idle > 0):
        reasons.append("growth_empty→file_lower_not_speed")
        # Prefer backoff path when fingerprint-quiet; otherwise hold (do not force 3m/5m).
        if quiet_hint and quiet_streak >= 1:
            target = max(target, 600)
        # else leave target at current — Mind still must act on refill_hint this cycle

    # Backoff: quiet fingerprint / long-running healthy work
    if quiet_hint and quiet_streak >= 3:
        # map streak to ladder step up from base 300
        if quiet_streak >= 11:
            target = 3600
        elif quiet_streak >= 6:
            target = 1200
        else:
            target = 600
        reasons.append("quiet_streak=%s→backoff" % quiet_streak)
    elif running_open > 0 and open_bags == running_open and idle_open == 0 and not board:
        # all open work is mid-run; avoid thrashing
        target = max(target, 600)
        reasons.append("all_open_running→≥10m")

    if posture_mode in ("standby", "dormant") and quiet_hint:
        target = max(target, 1200 if posture_mode == "standby" else 3600)
        reasons.append("posture_%s_quiet" % posture_mode)

    # snap to ladder
    if target not in ladder:
        target = min(ladder, key=lambda x: abs(x - target))

    action = "hold"
    if target < current:
        action = "shorten"
    elif target > current:
        action = "lengthen"

    return {
        "current_interval_sec": current,
        "recommended_interval_sec": target,
        "action": action,
        "base_interval_sec": 300,
        "min_interval_sec": 180,
        "ladder_sec": list(ladder),
        "reasons": reasons or ["hold"],
        "counts": {
            "open_bags": open_bags,
            "idle_open": idle_open,
            "running_open": running_open,
            "empty_idle": empty_idle,
            "product_open": counts["product_open"],
            "product_empty_idle": counts["product_empty_idle"],
            "starvation": starve,
            "wake_candidates": wake,
            "mail_wake_candidates": mail_wake,
            "runtime_bad": runtime_bad,
            "quiet_streak": quiet_streak,
            "growth_refill": bool(growth_refill),
        },
        "note": (
            "Mind applies cadence by replacing the FLEET_CYCLE scheduler. "
            "Empty growth bags → see refill_hint (file Head lower), not shorten."
        ),
    }


def _configured_model_fields(config: Any) -> Dict[str, Any]:
    if not isinstance(config, dict):
        return {}
    aliases = {
        "agent": ("agent",),
        "provider": ("provider",),
        "model": ("model", "agent_model"),
        "reasoning": ("reasoning", "agent_reasoning_effort", "thinking", "effort"),
    }
    result = {}
    for canonical, keys in aliases.items():
        for key in keys:
            item = config.get(key)
            if isinstance(item, (str, int, float, bool)) and str(item).strip():
                result[canonical] = item
                break
    return result


def _preferred_model_profile(fleet: Optional[dict], role: str, agent: Optional[str]) -> Dict[str, Any]:
    """Resolve only an exact, structurally unambiguous preferred-model profile."""
    preferred = fleet.get("preferred_models") if isinstance(fleet, dict) else None
    if not isinstance(preferred, dict):
        return {}
    if role == "head":
        profile = preferred.get("head")
        if not isinstance(profile, dict):
            return {}
        profile_agent = profile.get("agent")
        if profile_agent and agent and str(profile_agent).lower() != str(agent).lower():
            return {}
        return {
            key: value
            for key, value in _configured_model_fields(profile).items()
            if key in ("provider", "model", "reasoning")
        }
    if role != "hand" or not agent:
        return {}
    matches = [value for key, value in preferred.items() if str(key).lower() == str(agent).lower()]
    if len(matches) != 1 or not isinstance(matches[0], dict):
        return {}
    profile = matches[0].get("hand")
    if isinstance(profile, dict):
        return {
            key: value
            for key, value in _configured_model_fields(profile).items()
            if key in ("provider", "model", "reasoning")
        }
    if isinstance(profile, str) and profile.strip():
        return {"model": profile}
    return {}


def model_provenance(
    config: dict,
    observed: Optional[dict] = None,
    fleet: Optional[dict] = None,
    role: str = "hand",
) -> dict:
    configured = _preferred_model_profile(fleet, role, config.get("agent"))
    configured.update(_configured_model_fields(config))
    nested = _configured_model_fields(config.get("model_provenance"))
    configured.update(nested)
    observed = _model_fields(observed or {})
    comparable = sorted(set(configured).intersection(observed))
    if observed and configured:
        configured_model = configured.get("model")
        observed_model = observed.get("model")
        if configured_model is not None and observed_model is None:
            status = "unknown"
        elif configured_model is not None and configured_model != observed_model:
            status = "mismatch"
        elif not comparable:
            status = "unknown"
        else:
            status = "match" if all(configured[k] == observed[k] for k in comparable) else "mismatch"
    elif observed:
        status = "observed_only"
    elif configured:
        status = "configured_only"
    else:
        status = "unknown"
    return {"configured": configured or None, "observed": observed or None, "match_status": status}


_PRIVATE_KEYS = {
    "tail", "contents", "body", "message", "prompt", "completion", "customer",
    "subject", "board_status_raw_tail", "event", "evidence", "focus", "map_focus",
}


def redact_snapshot(value: Any) -> Any:
    """Conservatively remove content-bearing fields from persisted full snapshots."""
    if isinstance(value, dict):
        return {
            str(key): redact_snapshot(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).lower() not in _PRIVATE_KEYS
            and not any(token in str(key).lower() for token in ("secret", "token", "password", "credential"))
        }
    if isinstance(value, list):
        return [redact_snapshot(item) for item in value]
    return value


def summary_snapshot(out: dict) -> dict:
    roles = {}
    for group in ("heads", "hands"):
        for name, row in sorted((out.get(group) or {}).items()):
            runtime = row.get("runtime") or {}
            roles[name] = {
                "actionable": row.get("actionable"),
                "next_handle": row.get("next_handle"),
                "runtime_state": runtime.get("state"),
                "model_provenance": row.get("model_provenance"),
            }
    return {
        "fleet_id": out.get("fleet_id"),
        "fleet_posture": out.get("fleet_posture"),
        "signals": sorted(out.get("signals") or []),
        "quiet_hint": out.get("quiet_hint"),
        "partial": out.get("partial"),
        "fingerprint": redact_snapshot(out.get("fingerprint") or {}),
        "roles": roles,
    }


def _history_files(directory: Path) -> List[Path]:
    if not directory.is_dir():
        return []
    def cycle_key(path: Path) -> tuple:
        stem = path.stem
        return (0, int(stem), "") if stem.isdigit() else (1, 0, stem)
    return sorted((p for p in directory.glob("*.json") if p.is_file()), key=cycle_key)


def sensor_log_config(fleet: dict, project: Path) -> dict:
    raw = fleet.get("sensor_log") if isinstance(fleet.get("sensor_log"), dict) else {}
    location = raw.get("path") or raw.get("directory") or ".vivi/logs/sensors"
    path = Path(str(location)).expanduser()
    if not path.is_absolute():
        path = project / path
    return {
        "enabled": bool(raw.get("enabled", False)),
        "level": str(raw.get("level") or "off").lower(),
        "path": path.resolve(),
        "retention_cycles": raw.get("retention_cycles"),
    }


def read_history(directory: Path, limit: int, role: Optional[str]) -> List[dict]:
    records = []
    if limit <= 0:
        return records
    for path in _history_files(directory)[-limit:]:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if role:
            data = record.get("observation") or {}
            roles = data.get("roles") if isinstance(data, dict) else None
            if isinstance(roles, dict):
                data = dict(data)
                data["roles"] = {role: roles[role]} if role in roles else {}
            elif isinstance(data, dict):
                data = dict(data)
                for key in ("heads", "hands", "model_provenance"):
                    value = data.get(key)
                    if isinstance(value, dict):
                        data[key] = {role: value[role]} if role in value else {}
            record = dict(record)
            record["observation"] = data
        records.append(record)
    return records


class CycleConflictError(ValueError):
    pass


def record_history(out: dict, config: dict, cycle_id: str, recorded_at: str) -> dict:
    directory = config["path"]
    if not re.fullmatch(r"0|[1-9][0-9]*", cycle_id):
        raise ValueError("cycle id must be a canonical non-negative decimal integer")
    safe_id = cycle_id
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (safe_id + ".json")
    level = config["level"]
    if level == "summary":
        observation = summary_snapshot(out)
    elif level == "full":
        observation = redact_snapshot(out)
    else:
        previous = read_history(directory, 1, None)
        prior = ((previous[-1].get("observation") or {}).get("fingerprint") if previous else {}) or {}
        current = redact_snapshot(out.get("fingerprint") or {})
        observation = {
            "fleet_id": out.get("fleet_id"),
            "signals": sorted(out.get("signals") or []),
            "fingerprint": current,
            "material_diff": {
                key: {"before": prior.get(key), "after": current.get(key)}
                for key in sorted(set(prior).union(current))
                if prior.get(key) != current.get(key)
            },
            "model_provenance": {
                name: row.get("model_provenance")
                for group in ("heads", "hands")
                for name, row in sorted((out.get(group) or {}).items())
            },
        }
    record = {"schema_version": 1, "cycle_id": cycle_id, "cycle_at": recorded_at, "level": level, "observation": observation}
    encoded = (json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    status = "recorded"
    stored_bytes = len(encoded)
    pruned = []
    lock_path = directory / ".write.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if target.exists():
            existing_bytes = target.read_bytes()
            try:
                existing = json.loads(existing_bytes.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise CycleConflictError("existing cycle record is unreadable: %s" % exc)
            expected = {"schema_version": 1, "cycle_id": cycle_id, "level": level}
            actual = {key: existing.get(key) for key in expected} if isinstance(existing, dict) else {}
            if actual != expected:
                raise CycleConflictError(
                    "cycle %s conflicts with existing metadata: expected %r, found %r"
                    % (cycle_id, expected, actual)
                )
            status = "idempotent"
            stored_bytes = len(existing_bytes)
        else:
            fd, temporary = tempfile.mkstemp(prefix=".%s." % safe_id, suffix=".tmp", dir=str(directory))
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        keep = config.get("retention_cycles")
        if isinstance(keep, int) and not isinstance(keep, bool) and keep >= 0:
            files = _history_files(directory)
            for stale in files[:-keep] if keep else files:
                stale.unlink()
                pruned.append(stale.name)
    return {"status": status, "path": str(target), "bytes": stored_bytes, "pruned": pruned}


def format_text_summary(out: dict, fp: dict, git_main: dict) -> str:
    lines = [
        "fleet %s @ %s" % (out["fleet_id"], out["at"]),
        "focus: %s" % fp.get("map_focus"),
        "posture: %s" % ((out.get("fleet_posture") or {}).get("mode") or "growth"),
        "git: %s dirty=%s ahead=%s behind=%s"
        % (fp.get("swarm_head"), git_main.get("dirty"), git_main.get("ahead"), git_main.get("behind")),
        "operator_open=%s operator_to_mind=%s steward_armed=%s tripped=%s"
        % (
            (out.get("operator") or {}).get("open_count"),
            (out.get("operator") or {}).get("to_mind_count", 0),
            (out.get("steward") or {}).get("armed"),
            (out.get("steward") or {}).get("tripped"),
        ),
        "quiet_hint=%s signals=%s" % (out.get("quiet_hint"), out.get("signals")),
    ]
    rh = out.get("refill_hint") or {}
    if rh:
        lines.append(
            "refill: disposition=%s signal=%s — %s"
            % (
                rh.get("disposition"),
                rh.get("signal"),
                (rh.get("reason") or "")[:160],
            )
        )
        forbidden = rh.get("forbidden") or []
        if forbidden:
            lines.append("  refill_forbidden: %s" % ",".join(forbidden))
    ch = out.get("cadence_hint") or {}
    if ch:
        lines.append(
            "cadence: action=%s current=%ss recommend=%ss reasons=%s"
            % (
                ch.get("action"),
                ch.get("current_interval_sec"),
                ch.get("recommended_interval_sec"),
                ",".join(ch.get("reasons") or [])[:160],
            )
        )
    memos = (out.get("mind") or {}).get("memos") or []
    if memos:
        lines.append("mind_memos:")
        for memo in memos:
            lines.append("  %s: %s" % (memo.get("handle"), (memo.get("subject") or "")[:100]))
    for om in (out.get("operator") or {}).get("to_mind") or []:
        lines.append("  op→mind %s: %s" % (om.get("handle"), (om.get("subject") or "")[:80]))
    if git_main.get("dirty_paths"):
        lines.append("  dirty_paths: %s" % ", ".join(git_main.get("dirty_paths") or []))
    for rtm in (out.get("integration") or {}).get("pending_rtm") or []:
        lines.append(
            "  pending_rtm %s from=%s commit=%s: %s"
            % (rtm.get("handle"), rtm.get("from"), rtm.get("commit"), (rtm.get("subject") or "")[:90])
        )
    for name, h in (out.get("hands") or {}).items():
        stall_n = int(h.get("cycles_unchanged") or 0)
        stall_lab = " stall=%s" % stall_n if stall_n > 0 else ""
        lane = h.get("lane_progress") if isinstance(h.get("lane_progress"), dict) else {}
        lane_lab = " lane=%s" % lane.get("reason") if lane.get("candidate") else ""
        lines.append(
            "  %s: bag=%s next=%s state=%s%s%s target=%s"
            % (
                name,
                h.get("actionable"),
                h.get("next_handle"),
                (h.get("runtime") or {}).get("state"),
                stall_lab,
                lane_lab,
                (h.get("runtime") or {}).get("target"),
            )
        )
    for name, hd in (out.get("heads") or {}).items():
        if not hd.get("sweep_enabled"):
            continue
        if hd.get("sweep_due"):
            extra = " DUE"
        elif hd.get("sweep_overdue_sec") is not None:
            extra = " overdue=%ss" % hd.get("sweep_overdue_sec")
        else:
            extra = ""
        n_loops = hd.get("sweep_every_n_loops")
        sweep_lab = "%ss" % hd.get("sweep_interval")
        if n_loops is not None:
            sweep_lab = "×%s loops (%ss)" % (n_loops, hd.get("sweep_interval"))
        lines.append(
            "  %s: state=%s sweep=%s last=%s%s target=%s"
            % (
                name,
                (hd.get("runtime") or {}).get("state"),
                sweep_lab,
                (hd.get("sweep_last_completed") or "never")[:19],
                extra,
                (hd.get("runtime") or {}).get("target"),
            )
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fleet cheap sensors snapshot (Python 3.9+; macOS/Linux)")
    add_fleet_scope_arguments(ap, include_role=True)
    ap.add_argument("--json", action="store_true", default=True, help="JSON output (default)")
    ap.add_argument("--text", action="store_true", help="Human text summary instead of JSON")
    ap.add_argument("--no-watch", action="store_true", help="Skip mailspace watch --once")
    ap.add_argument("--tail", type=int, default=16, help="tmux capture lines per pane")
    ap.add_argument("--memo-limit", type=int, default=20, help="number of Mind memo checklist lines to include; 0 disables")
    ap.add_argument("--cursor-file", default=None, help="watch cursor path (default: .vivi/mind-watch.cursor)")
    ap.add_argument("--record-cycle", action="store_true", help="Record this canonical Mind-cycle observation when sensor_log is enabled")
    ap.add_argument("--cycle-id", default=None, help="Cycle identifier (default: next baseline cycle)")
    ap.add_argument("--history", type=int, metavar="N", help="Read the last N recorded cycles without collecting sensors")
    args = ap.parse_args()
    selected_role = args.role[0] if args.role else None
    if args.role and len(args.role) != 1:
        ap.error("--role may be specified once for --history")
    if selected_role and args.history is None:
        ap.error("--role requires --history")
    if args.cycle_id is not None and not args.record_cycle:
        ap.error("--cycle-id requires --record-cycle")
    if args.history is not None and (args.record_cycle or args.cycle_id is not None or args.text):
        ap.error("--history cannot be combined with --record-cycle, --cycle-id, or --text")
    if args.cycle_id is not None and not re.fullmatch(r"0|[1-9][0-9]*", args.cycle_id):
        ap.error("--cycle-id must be a canonical non-negative decimal integer")
    if args.memo_limit < 0:
        ap.error("--memo-limit must be non-negative")

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(json.dumps({"error": "project not a directory: %s" % project}), file=sys.stderr)
        return 1

    try:
        fleet_path, fleet = resolve_fleet_file(project, args.fleet, args.fleet_file)
    except FleetScopeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    baseline_path = project / ".vivi" / "mind-baseline.json"
    baseline = load_json(baseline_path)
    log_config = sensor_log_config(fleet, project)
    if args.history is not None:
        if args.history < 0:
            ap.error("--history must be non-negative")
        selected = read_history(log_config["path"], args.history, None)
        if selected_role:
            known_roles = set()
            role_aliases = {}
            for name, block in (fleet.get("hands") or fleet.get("hunters") or {}).items():
                canonical = str(name)
                known_roles.add(canonical)
                role_aliases[canonical] = canonical
                if isinstance(block, dict) and block.get("mail_identity"):
                    alias = str(block["mail_identity"])
                    known_roles.add(alias)
                    role_aliases[alias] = canonical
            nested_heads = fleet.get("heads") if isinstance(fleet.get("heads"), dict) else {}
            for name, block in list(nested_heads.items()) + list(fleet.items()):
                if str(name).startswith("head-") and isinstance(block, dict):
                    canonical = str(name)
                    known_roles.add(canonical)
                    role_aliases[canonical] = canonical
                    if block.get("mail_identity"):
                        alias = str(block["mail_identity"])
                        known_roles.add(alias)
                        role_aliases[alias] = canonical
            for record in selected:
                observation = record.get("observation") if isinstance(record, dict) else None
                if not isinstance(observation, dict):
                    continue
                for key in ("roles", "heads", "hands", "model_provenance"):
                    value = observation.get(key)
                    if isinstance(value, dict):
                        for name in value:
                            known_roles.add(str(name))
                            role_aliases.setdefault(str(name), str(name))
            if selected_role not in known_roles:
                ap.error("unknown --role %r (known roles: %s)" % (selected_role, ", ".join(sorted(known_roles)) or "none"))
            selected = read_history(log_config["path"], args.history, role_aliases[selected_role])
        print(json.dumps({"schema_version": 1, "history": selected}, indent=2, ensure_ascii=False))
        return 0
    # previous fingerprint — quiet-sleep only (not head report bookkeeping)
    prev = baseline.get("last_actionable_fingerprint") or {}
    if not isinstance(prev, dict):
        prev = {}
    tooling = fleet.get("tooling") or {}

    vivi = which("vivi", tooling, "vivi") or which("vivi")
    tmux = resolve_tmux_bin(tooling if isinstance(tooling, dict) else None)
    mind_inbox = fleet.get("mind_inbox") or "mind"
    operator_inbox = fleet.get("operator_inbox") or "operator"
    # Heads report To mind@; legacy fleets may set head_report_inbox: reviewer.
    head_report_inbox = fleet.get("head_report_inbox") or "mind"
    hands = fleet.get("hands") or fleet.get("hunters") or {}

    partial = False
    out = {
        "ok": True,
        "at": now_iso(),
        "project": str(project),
        "fleet_id": fleet.get("fleet_id") or fleet.get("mailspace") or project.name,
        "fleet_json": str(fleet_path),
        "focus": fleet.get("focus") or {},
        "identities": {},
        "hands": {},
        "heads": {},
        "steward": {},
        "operator": {},
        "mind": {},
        "integration": {},
        "git": {},
        "watch": None,
        "fingerprint": {},
        "quiet_hint": False,
        "signals": [],
        "python": "%d.%d.%d" % sys.version_info[:3],
        "platform": sys.platform,
    }  # type: Dict[str, Any]

    # --- board status ---
    status_text = ""
    if vivi:
        rc, status_text = run([vivi, "mailspace", "status", "--project", str(project)], timeout=25)
        out["identities"] = parse_status_table(status_text)
        out["board_status_raw_tail"] = "\n".join(status_text.splitlines()[:40])
        if rc != 0:
            partial = True
            out["signals"].append("vivi_status_failed")
    else:
        partial = True
        out["signals"].append("vivi_missing")

    # --- watch ---
    if vivi and not args.no_watch:
        cursor = args.cursor_file or str(project / ".vivi" / "mind-watch.cursor")
        rc, wout = run(
            [
                vivi,
                "mailspace",
                "watch",
                "--for",
                mind_inbox,
                "--project",
                str(project),
                "--once",
                "--write-cursor",
                "--cursor-file",
                cursor,
            ],
            timeout=15,
        )
        out["watch"] = {"rc": rc, "event": wout.strip()[:500] if wout.strip() else None}
        if wout.strip() and "event=" in wout:
            out["signals"].append("board_event")

    # --- operator (two directions) ---
    # 1) To operator@ — escalations waiting on the human
    # 2) From operator@ To mind@ — human decisions/feedback Mind must absorb first
    op_row = out["identities"].get(operator_inbox) or {}
    op_handles = []
    op_to_mind = []  # type: List[Dict[str, str]]
    if vivi:
        op_handles = list_open_handles(vivi, str(project), operator_inbox, "need")
        # mail list may not mark open the same way — count inbox unread from status
        op_to_mind = list_mail_from_operator(
            vivi, str(project), mind_inbox, operator_inbox, limit=15
        )
    out["operator"] = {
        "identity": operator_inbox,
        "needs_open": op_row.get("needs_open", 0),
        "inbox_unread": op_row.get("inbox_unread", 0),
        "needs": op_handles,
        # To-operator bag (human backlog)
        "open_count": (op_row.get("needs_open") or 0) + (op_row.get("inbox_unread") or 0),
        # From-operator → mind (feedback / decisions)
        "to_mind": op_to_mind,
        "to_mind_count": len(op_to_mind),
    }
    if out["operator"]["open_count"]:
        out["signals"].append("operator_mail")  # waiting on human
    if op_to_mind:
        out["signals"].append("operator_to_mind")  # human wrote Mind — absorb first

    mind_row = out["identities"].get(mind_inbox) or {}
    mind_memos = list_memos(vivi, str(project), mind_inbox, limit=args.memo_limit) if vivi else []
    out["mind"] = {
        "identity": mind_inbox,
        "inbox_unread": mind_row.get("inbox_unread", 0),
        "from_operator": op_to_mind,
        "from_operator_count": len(op_to_mind),
        "memos": mind_memos,
        "memo_count": len(mind_memos),
        "memo_limit": args.memo_limit,
    }

    now_dt = datetime.now(timezone.utc)

    # --- fleet posture (continuity vs sleep) ---
    (
        posture_mode,
        posture_suppresses_starvation,
        posture_pauses_executive_sweeps,
        posture_out,
    ) = resolve_posture(fleet, baseline)
    out["fleet_posture"] = posture_out

    coo_open_tasks = list_open_handles(vivi, str(project), "head-coo", "task") if vivi else []
    dr_state, dr_signals = evaluate_disaster_recovery(fleet, baseline, posture_mode, now_dt, coo_open_tasks)
    if dr_state is not None:
        out["disaster_recovery"] = dr_state
        out["signals"].extend(dr_signals)

    # --- hands panes + bag ---
    runtime_states = {}  # type: Dict[str, str]
    # stall-risk: track per-hand pane-tail stability across cycles so a frozen
    # pane with open assigned work surfaces as a signal even when the pane
    # classifier (a brittle string matcher) mis-reads it as idle. State rides in
    # baseline.hand_progress, persisted by fleet-baseline.py bump.
    _php = baseline.get("hand_progress")
    prev_hand_progress = _php if isinstance(_php, dict) else {}
    stall_floor = int(fleet.get("stall_risk_cycles_floor") or 3)
    hand_progress = {}  # type: Dict[str, Dict[str, Any]]
    lane_policy = fleet.get("lane_lifecycle") if isinstance(fleet.get("lane_lifecycle"), dict) else {}
    try:
        lane_stale_floor = max(1, int(lane_policy.get("stale_after_cycles") or 5))
    except (TypeError, ValueError):
        lane_stale_floor = 5
    try:
        lane_resume_hours = max(0, int(lane_policy.get("resume_stale_after_hours") or 24))
    except (TypeError, ValueError):
        lane_resume_hours = 24
    _plp = baseline.get("lane_progress")
    prev_lane_progress = _plp if isinstance(_plp, dict) else {}
    lane_progress = {}  # type: Dict[str, Dict[str, Any]]
    if tmux and (Path(tmux).is_file() or shutil.which(tmux)):
        tmux_bin = tmux if Path(tmux).is_file() else (shutil.which(tmux) or tmux)
    else:
        tmux_bin = shutil.which("tmux") or ""
    vivi_pty_bin = shutil.which("vivi-pty") or ""

    for name, h in hands.items():
        if not isinstance(h, dict):
            continue
        mid = h.get("mail_identity") or name
        runtime = h.get("runtime") or {}
        vivi_pty_role = is_vivi_pty_role(h)
        if vivi_pty_role:
            session_id = (runtime.get("session_id") if isinstance(runtime, dict) else None) or mid
            socket = (runtime.get("socket") if isinstance(runtime, dict) else None) or str(project / ".vivi" / "vivi-pty.sock")
            target = session_id
            session = socket
        else:
            target = h.get("tmux_target") or ("%s:1.1" % (h.get("tmux_session") or name))
            session = target.split(":")[0]
        cwd = h.get("cwd") or str(project)
        agent = h.get("agent") or "unknown"
        row = out["identities"].get(mid) or {}
        open_tasks = list_open_handles(vivi, str(project), mid, "task") if vivi else []
        open_needs = list_open_handles(vivi, str(project), mid, "need") if vivi else []
        addressed_mail = list_recent_mail(vivi, str(project), mid, limit=1) if vivi else []
        mail_top_handle = addressed_mail[0]["handle"] if addressed_mail else None
        previous_mail_top = prev.get("%s_mail_top" % name.replace("-", "_"))
        new_addressed_mail = bool(
            mail_top_handle and previous_mail_top and mail_top_handle != previous_mail_top
        )
        previous_mail_pending = prev.get("%s_mail_pending" % name.replace("-", "_"))
        wake_by_hand = ((baseline.get("last_hand_wake") or {}).get("by_hand") or {}).get(name) or {}
        last_wake_handle = wake_by_hand.get("handle")
        mail_pending_handle = (
            mail_top_handle
            if new_addressed_mail
            else previous_mail_pending
            if previous_mail_pending and previous_mail_pending != last_wake_handle
            else None
        )
        bag_open = (row.get("tasks_open") or len(open_tasks)) + (row.get("needs_open") or len(open_needs))

        sess_ok = False
        tail = ""
        runtime_state = None
        process_state = "unknown"
        runtime_confidence = "medium"
        runtime_evidence = []
        observed_model = {}
        if vivi_pty_role:
            if not vivi_pty_bin:
                partial = True
                out["signals"].append("vivi_pty_missing")
            else:
                captured = capture_vivi_pty(target, session, vivi_pty_bin)
                sess_ok = captured["exists"]
                tail = captured["tail"]
                runtime_state = captured["state"]
                process_state = captured["process_state"]
                runtime_confidence = captured["confidence"]
                runtime_evidence = captured["evidence"]
                observed_model = captured.get("model") or {}
                if not sess_ok and not tail:
                    partial = True
        elif tmux_bin:
            rc, _ = run(
                [tmux_bin, "has-session", "-t", exact_tmux_session(session)],
                timeout=5,
            )
            sess_ok = rc == 0
            if sess_ok:
                rc, tail = run(
                    [
                        tmux_bin,
                        "capture-pane",
                        "-t",
                        exact_tmux_target(target),
                        "-p",
                        "-S",
                        "-%d" % args.tail,
                    ],
                    timeout=5,
                )
                if rc != 0:
                    tail = ""
                    partial = True

        pclass = (
            classify_vivi_pty(runtime_state or "unknown", tail, sess_ok)
            if vivi_pty_role
            else classify_terminal(tail, sess_ok)
        )
        if not vivi_pty_role:
            process_state = "running" if sess_ok else "stopped"
        runtime_states[name] = pclass
        next_handle = open_tasks[0]["handle"] if open_tasks else (open_needs[0]["handle"] if open_needs else None)

        if pclass in ("failed", "stopped", "approval_required"):
            out["signals"].append(f"runtime_{name}_{pclass}")
        packet = h.get("packet") if isinstance(h.get("packet"), dict) else {}
        pkt_state = str(packet.get("state") or "").lower()
        paused_pkt = pkt_state.startswith("paused") or pkt_state in ("hold", "operational_pause")
        hand_paused = hand_is_paused(baseline, name)
        if (
            bag_open
            and pclass in ("waiting_for_input", "completed", "unknown")
            and not hand_paused
            and not paused_pkt
        ):
            out["signals"].append(f"wake_candidate_{name}")
        if new_addressed_mail:
            out["signals"].append(f"mail_for_{name}")
        if mail_pending_handle and pclass in ("waiting_for_input", "completed", "unknown") and not hand_paused and not paused_pkt:
            out["signals"].append(f"mail_wake_candidate_{name}")
        # Starvation is a candidate only — suppress when fleet/baseline marks intentional pause
        if (
            bag_open == 0
            and pclass in ("waiting_for_input", "completed")
            and not paused_pkt
            and not hand_paused
            and not posture_suppresses_starvation
        ):
            out["signals"].append(f"starvation_candidate_{name}")

        # stall-risk: hash the captured pane tail and compare to the previous
        # cycle's hash. A byte-stable tail while open work is assigned is the
        # harness-agnostic signature of a stuck pane (permission dialog, frozen
        # spinner, silent error) that the pane classifier may mis-read as idle.
        pane_tail_text = "\n".join((tail or "").splitlines()[-args.tail :])
        pane_tail_hash = (
            hashlib.sha1(pane_tail_text.encode("utf-8", "ignore")).hexdigest()[:16]
            if pane_tail_text
            else None
        )
        prev_hp = prev_hand_progress.get(name)
        prev_hp = prev_hp if isinstance(prev_hp, dict) else {}
        prev_hash = prev_hp.get("tail_hash")
        if pane_tail_hash and prev_hash and pane_tail_hash == prev_hash:
            cycles_unchanged = int(prev_hp.get("cycles_unchanged") or 0) + 1
        else:
            cycles_unchanged = 0
        hand_progress[name] = {
            "tail_hash": pane_tail_hash,
            "cycles_unchanged": cycles_unchanged,
            "has_open_work": bool(bag_open),
            "state": pclass,
        }
        if (
            bag_open
            and cycles_unchanged >= stall_floor
            and pclass not in ("starting", "submitting", "running")
            and not hand_paused
            and not paused_pkt
        ):
            out["signals"].append(f"stall_risk_{name}")

        hand_row = {
            "mail_identity": mid,
            "agent": agent,
            "cwd": cwd,
            "tasks_open": row.get("tasks_open", len(open_tasks)),
            "needs_open": row.get("needs_open", len(open_needs)),
            "actionable": row.get("actionable", bag_open),
            "open_tasks": open_tasks,
            "open_needs": open_needs,
            "next_handle": next_handle,
            "mail_top_handle": mail_top_handle,
            "mail_pending_handle": mail_pending_handle,
            "new_addressed_mail": new_addressed_mail,
            "cycles_unchanged": cycles_unchanged,
            "min_seconds_between_wakes": h.get("min_seconds_between_wakes", 180),
            "merges_to_main": h.get("merges_to_main", False),
            "packet_state": packet.get("state"),
            "operational_pause": hand_paused or paused_pkt,
        }
        runtime_observation = {
            "kind": "vivi_pty" if vivi_pty_role else "tmux",
            "target": target,
            "state": pclass,
            "process_state": process_state,
            "confidence": runtime_confidence,
            "evidence": runtime_evidence,
            "tail": pane_tail_text,
            "tail_hash": pane_tail_hash,
        }
        if pclass == "failed":
            runtime_observation["detail"] = failure_detail(tail)
        if vivi_pty_role:
            runtime_observation["socket"] = session
        hand_row["runtime"] = runtime_observation
        hand_row["model_provenance"] = model_provenance(h, observed_model, fleet, "hand")
        out["hands"][name] = hand_row

        binding = lane_binding(h)
        if binding:
            host = str(h.get("host") or "local").lower()
            remote = host not in ("", "local") or bool(h.get("ssh"))
            git_state = lane_git_state(cwd, remote=remote)
            binding_state = str(binding.get("state") or "").lower()
            wake_trigger = binding.get("wake_trigger") or binding.get("wake_triggers")
            intentionally_parked = binding_state in ("parked", "deferred", "blocked", "hold") and bool(wake_trigger)
            signature = lane_progress_signature(
                binding,
                open_tasks,
                open_needs,
                mail_top_handle,
                git_state,
            )
            progress = lane_progress_observation(
                prev_lane_progress.get(name) if isinstance(prev_lane_progress.get(name), dict) else {},
                signature,
                now_dt,
                lane_stale_floor,
                lane_resume_hours,
                pclass,
                bool(bag_open),
                intentionally_parked,
            )
            progress.update({
                "binding": binding,
                "git": git_state,
                "has_open_work": bool(bag_open),
            })
            lane_progress[name] = progress
            hand_row["lane_progress"] = progress
            if progress["candidate"]:
                out["signals"].append(f"lane_reconcile_candidate_{name}")

        # git for main hand (walk up from cwd; container fleets scan children / git.main_cwd)
        if h.get("merges_to_main") or name == fleet.get("default_hand"):
            out["git"]["main"] = git_tip(Path(cwd), fleet)

    out["hand_progress"] = hand_progress
    out["lane_progress"] = lane_progress

    # RTM is mail rather than an open bag item. Surface unmerged RTM mail so
    # empty Hand bags cannot masquerade as honest product starvation.
    rtm_mail = list_ready_to_merge(vivi, str(project), mind_inbox) if vivi else []
    recent_mail = list_recent_mail(vivi, str(project), mind_inbox) if vivi and rtm_mail else []
    git_main = (out.get("git") or {}).get("main") or {}
    main_cwd = git_main.get("cwd")
    main_name = fleet.get("default_hand") or "hand-1"
    main_cfg = hands.get(main_name) if isinstance(hands.get(main_name), dict) else {}
    main_identity = main_cfg.get("mail_identity") or main_name
    pending_rtm = []
    merged_rtm = []
    unresolved_rtm = []
    for item in rtm_mail:
        ancestry = commit_is_on_main(main_cwd, item.get("commit"))
        enriched = dict(item)
        enriched["commit_on_main"] = ancestry
        completion = rtm_completion_mail(item, recent_mail, main_identity)
        enriched["completion_mail"] = completion
        if ancestry is True or completion:
            merged_rtm.append(enriched)
        elif ancestry is False or git_main.get("dirty"):
            pending_rtm.append(enriched)
        else:
            unresolved_rtm.append(enriched)
    out["integration"] = {
        "pending_rtm": pending_rtm,
        "pending_rtm_count": len(pending_rtm),
        "merged_rtm_count": len(merged_rtm),
        "unresolved_rtm_count": len(unresolved_rtm),
        "suggested_actions": (["queue_merge_to_main_hand"] if pending_rtm else []),
    }
    if pending_rtm:
        out["signals"].append("pending_rtm")
        out["signals"].append("integration_lag")

    # heads (optional pane scan) + executive cadence.
    # Single dial: executive_cadence.every_n_loops
    #   0     = on-call (no head_due_* from schedule)
    #   N>=1  = scheduled every N × mind_loop.interval_sec
    # Due when scheduled, interval elapsed since last report, pane not mid-pass.
    # Completion: new mail from head identity/legacy_aliases in head_report_inbox.
    # Legacy enabled true/false folded into every_n_loops resolution; self_directed ignored.
    loop_sec = int(posture_out.get("mind_loop_interval_sec") or mind_loop_interval_sec(fleet))
    head_blocks = {}
    nested_heads = fleet.get("heads") if isinstance(fleet.get("heads"), dict) else {}
    for key, block in nested_heads.items():
        if str(key).startswith("head-") and isinstance(block, dict):
            head_blocks[str(key)] = block
    for key, block in fleet.items():
        if str(key).startswith("head-") and isinstance(block, dict):
            head_blocks[str(key)] = block
    tmux_required = any(
        isinstance(slot, dict) and not is_vivi_pty_role(slot) for slot in hands.values()
    ) or any(not is_vivi_pty_role(block) for block in head_blocks.values())
    if bool((fleet.get("steward") or {}).get("enabled")):
        tmux_required = True
    if tmux_required and not tmux_bin:
        partial = True
        out["signals"].append("tmux_missing")

    for key, block in sorted(head_blocks.items()):
        runtime = block.get("runtime") or {}
        vivi_pty_role = is_vivi_pty_role(block)
        if vivi_pty_role:
            target = (runtime.get("session_id") if isinstance(runtime, dict) else None) or block.get("mail_identity") or key
            session = (runtime.get("socket") if isinstance(runtime, dict) else None) or str(project / ".vivi" / "vivi-pty.sock")
        else:
            target = block.get("tmux_target") or f"{block.get('tmux_session') or key}:1.1"
            session = target.split(":")[0]
        sess_ok = False
        tail = ""
        runtime_state = None
        process_state = "unknown"
        runtime_confidence = "medium"
        runtime_evidence = []
        observed_model = {}
        if vivi_pty_role:
            if not vivi_pty_bin:
                partial = True
                out["signals"].append("vivi_pty_missing")
            else:
                captured = capture_vivi_pty(target, session, vivi_pty_bin)
                sess_ok = captured["exists"]
                tail = captured["tail"]
                runtime_state = captured["state"]
                process_state = captured["process_state"]
                runtime_confidence = captured["confidence"]
                runtime_evidence = captured["evidence"]
                observed_model = captured.get("model") or {}
        elif tmux_bin:
            rc, _ = run(
                [tmux_bin, "has-session", "-t", exact_tmux_session(session)],
                timeout=5,
            )
            sess_ok = rc == 0
            if sess_ok:
                _, tail = run(
                    [
                        tmux_bin,
                        "capture-pane",
                        "-t",
                        exact_tmux_target(target),
                        "-p",
                        "-S",
                        "-%d" % min(args.tail, 12),
                    ],
                    timeout=5,
                )
        pclass = (
            classify_vivi_pty(runtime_state or "unknown", tail, sess_ok)
            if vivi_pty_role
            else classify_terminal(tail, sess_ok)
        )
        if not vivi_pty_role:
            process_state = "running" if sess_ok else "stopped"
        runtime_states[key] = pclass

        addressed_mail = list_recent_mail(vivi, str(project), block.get("mail_identity") or key, limit=1) if vivi else []
        mail_top_handle = addressed_mail[0]["handle"] if addressed_mail else None
        previous_mail_top = prev.get("%s_mail_top" % key.replace("-", "_"))
        new_addressed_mail = bool(
            mail_top_handle and previous_mail_top and mail_top_handle != previous_mail_top
        )
        previous_mail_pending = prev.get("%s_mail_pending" % key.replace("-", "_"))
        wake_by_hand = ((baseline.get("last_hand_wake") or {}).get("by_hand") or {}).get(key) or {}
        last_wake_handle = wake_by_hand.get("handle")
        mail_pending_handle = (
            mail_top_handle
            if new_addressed_mail
            else previous_mail_pending
            if previous_mail_pending and previous_mail_pending != last_wake_handle
            else None
        )

        cad = block.get("executive_cadence") if isinstance(block.get("executive_cadence"), dict) else {}
        every_n = resolve_head_every_n_loops(posture_mode, key, cad)
        # 0 = on-call; N>=1 = scheduled for Mind to wake when due
        sweep_enabled = every_n >= 1
        sweep_interval = head_sweep_interval_sec(fleet, posture_mode, key, every_n)
        # Explicit config wins for mode string; else posture default.
        sweep_mode = cad.get("sweep_mode") or posture_out.get("default_head_sweep_mode")
        sender_tokens = [block.get("mail_identity") or key]
        la = block.get("legacy_aliases")
        if isinstance(la, list):
            sender_tokens += [str(x) for x in la]
        elif isinstance(la, str):
            sender_tokens.append(la)
        recent = (
            list_mail_from_identity(vivi, str(project), head_report_inbox, sender_tokens, limit=5)
            if (sweep_enabled and vivi)
            else []
        )
        cur_top = recent[0]["handle"] if recent else None
        top_date = recent[0].get("date") if recent else None

        # Prefer documented baseline head-* report keys; one-shot migrate from
        # legacy fingerprint head_*_last_* if baseline block is empty.
        prev_hb = head_state_block(baseline, key)
        prev_last_handle = prev_hb.get("last_report_handle")
        prev_last_completed = prev_hb.get("last_report_at")
        pk = key.replace("-", "_")  # head_ceo
        if prev_last_handle is None and prev_last_completed is None:
            prev_last_handle = prev.get("%s_last_handle" % pk)
            prev_last_completed = prev.get("%s_last_completed" % pk)

        completed_this_cycle = False
        if prev_last_handle is None and prev_last_completed is None:
            # bootstrap: seed from existing history (real mail date when available)
            last_handle = cur_top
            last_completed = top_date if cur_top else None
        elif cur_top is not None and cur_top != prev_last_handle:
            completed_this_cycle = True
            last_handle = cur_top
            last_completed = top_date or now_iso()
        else:
            last_handle = prev_last_handle
            last_completed = prev_last_completed

        head_paused = head_is_paused(baseline, key)

        secs = _secs_since(last_completed, now_dt) if last_completed else None
        interval_elapsed = (secs is None) or (secs >= sweep_interval)
        # dormant pauses Head cadence; standby still allows stewardship sweeps.
        sweep_due = (
            sweep_enabled
            and not head_paused
            and not posture_pauses_executive_sweeps
            and pclass not in ("starting", "submitting", "running")
            and interval_elapsed
        )
        overdue_sec = None
        if (
            sweep_enabled
            and not posture_pauses_executive_sweeps
            and secs is not None
            and secs > sweep_interval
        ):
            overdue_sec = int(secs - sweep_interval)

        short = pk.split("_", 1)[1]  # ceo | cto | cxo
        if sweep_due:
            out["signals"].append("head_due_%s" % short)
        if new_addressed_mail:
            out["signals"].append("mail_for_%s" % key)
        if mail_pending_handle and pclass in ("waiting_for_input", "completed", "unknown") and not head_paused:
            out["signals"].append("mail_wake_candidate_%s" % key)
        if pclass in ("failed", "stopped", "approval_required"):
            out["signals"].append("runtime_%s_%s" % (key, pclass))

        head_tail = "\n".join((tail or "").splitlines()[-8:])
        head_row = {
            "mail_top_handle": mail_top_handle,
            "mail_pending_handle": mail_pending_handle,
            "new_addressed_mail": new_addressed_mail,
            "sweep_enabled": sweep_enabled,
            "sweep_mode": sweep_mode,
            "sweep_interval": sweep_interval,
            "sweep_every_n_loops": every_n,
            "mind_loop_interval_sec": loop_sec,
            "sweep_due": sweep_due,
            "sweep_overdue_sec": overdue_sec,
            "sweep_completed_this_cycle": completed_this_cycle,
            "sweep_last_completed": last_completed,
            "sweep_last_handle": last_handle,
            "sweep_top_handle": cur_top,
            "sweep_paused": head_paused or posture_pauses_executive_sweeps,
        }
        runtime_observation = {
            "kind": "vivi_pty" if vivi_pty_role else "tmux",
            "target": target,
            "state": pclass,
            "process_state": process_state,
            "confidence": runtime_confidence,
            "evidence": runtime_evidence,
            "tail": head_tail,
            "tail_hash": hashlib.sha1(head_tail.encode("utf-8", "ignore")).hexdigest()[:16] if head_tail else None,
        }
        if pclass == "failed":
            runtime_observation["detail"] = failure_detail(tail)
        if vivi_pty_role:
            runtime_observation["socket"] = session
        head_row["runtime"] = runtime_observation
        head_row["model_provenance"] = model_provenance(block, observed_model, fleet, "head")
        out["heads"][key] = head_row

    dr_state = out.get("disaster_recovery")
    coo_runtime = ((out.get("heads") or {}).get("head-coo") or {}).get("runtime") or {}
    if isinstance(dr_state, dict) and coo_runtime.get("state") in ("starting", "submitting", "running"):
        assignment = dr_state.setdefault("assignment", {})
        assignment["runtime_backpressure"] = True
        if assignment.get("action") == "none":
            assignment["action"] = "suppress_duplicate_runtime_busy"

    # steward block from fleet + baseline + optional pane
    st_cfg = fleet.get("steward") or {}
    st_base = baseline.get("steward") or {}
    st_target = st_cfg.get("tmux_target") or ("%s:1.1" % (st_cfg.get("tmux_session") or "steward"))
    st_session = st_target.split(":")[0]
    st_sess_ok = False
    st_tail = ""
    if tmux_bin:
        rc, _ = run(
            [tmux_bin, "has-session", "-t", exact_tmux_session(st_session)],
            timeout=5,
        )
        st_sess_ok = rc == 0
        if st_sess_ok:
            _, st_tail = run(
                [
                    tmux_bin,
                    "capture-pane",
                    "-t",
                    exact_tmux_target(st_target),
                    "-p",
                    "-S",
                    "-8",
                ],
                timeout=5,
            )
    st_class = classify_terminal(st_tail, st_sess_ok)
    runtime_states["steward"] = st_class
    last_ok = (baseline.get("mind_loop") or {}).get("last_successful_cycle_at") or st_base.get(
        "last_rearm_at"
    )
    out["steward"] = {
        # Default OFF — match steward.sh and process law (opt-in dead-man).
        "enabled": st_cfg.get("enabled", False),
        "armed": bool(st_base.get("armed")),
        "tripped": bool(st_base.get("tripped")),
        "runtime": {
            "kind": "tmux",
            "target": st_target,
            "state": st_class,
            "process_state": "running" if st_sess_ok else "stopped",
            "confidence": "medium",
            "evidence": [],
            "tail": "\n".join((st_tail or "").splitlines()[-8:]),
        },
        "last_successful_cycle_at": last_ok,
        "last_rearm_at": st_base.get("last_rearm_at"),
        "grace_sec": st_cfg.get("grace_sec", 900),
    }
    if out["steward"]["tripped"]:
        out["signals"].append("steward_tripped")

    # fingerprint + quiet (due flags only; durable head reports on baseline head-*)
    git_main = out.get("git", {}).get("main") or {}
    fp = build_fingerprint(out, fleet)
    out["fingerprint"] = fp
    out["runtime_states"] = runtime_states
    # Growth empty product bags → explicit refill disposition (Head lower), not quiet/speed.
    refill = refill_hint_from(out, out["signals"], posture_suppresses_starvation)
    if refill:
        out["refill_hint"] = refill
        if refill.get("signal") and refill["signal"] not in out["signals"]:
            out["signals"].append(str(refill["signal"]))
    else:
        out["refill_hint"] = None
    out["quiet_hint"] = quiet_hint_from(fp, prev, out["signals"], out["steward"])
    out["cadence_hint"] = cadence_hint_from(out, baseline, out["quiet_hint"], out["signals"])
    out["baseline_last_cycle"] = baseline.get("last_cycle")
    out["baseline_mind_mode"] = baseline.get("mind_mode")
    out["partial"] = partial
    out["ok"] = not partial or bool(out["hands"])

    out["sensor_log"] = {
        "enabled": log_config["enabled"],
        "level": log_config["level"],
        "path": str(log_config["path"]),
        "status": "not_requested",
    }
    if args.record_cycle:
        if not log_config["enabled"] or log_config["level"] == "off":
            out["sensor_log"]["status"] = "disabled"
        else:
            try:
                cycle_id = args.cycle_id or str(max(0, int(baseline.get("last_cycle") or 0) + 1))
                out["sensor_log"].update(record_history(out, log_config, cycle_id, out["at"]))
                out["sensor_log"]["cycle_id"] = cycle_id
            except (OSError, UnicodeError, ValueError, TypeError) as exc:
                partial = True
                out["signals"].append("sensor_log_failed")
                status = "conflict" if isinstance(exc, CycleConflictError) else "failed"
                out["sensor_log"].update({"status": status, "error": str(exc)})
                out["partial"] = True
                out["ok"] = not partial or bool(out["hands"])

    if args.text:
        print(format_text_summary(out, fp, git_main))
    else:
        print(json.dumps(out, indent=2, ensure_ascii=False))

    return 2 if partial else 0


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
