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
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import load_json as _load_json  # noqa: E402
from fleet_common import now_iso, require_python, run_cmd, which  # noqa: E402

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


def classify_pane(text: str, session_exists: bool) -> str:
    """running|idle_prompt|done_idle|trust_prompt|error_capacity|error_connection|down|unknown"""
    if not session_exists:
        return "down"
    t = text or ""
    if re.search(r"Working \(|esc to interrupt|Waiting for response|Responding…|Responding\.\.\.|Thinking…", t, re.I):
        return "running"
    if re.search(
        r"Yes, continue|Do you trust|trust this workspace|No, quit|Press enter to continue"
        r"|Always allow|Allow always|Allow once|until OpenCode is restarted",
        t,
        re.I,
    ):
        return "trust_prompt"
    if re.search(r"over capacity|rate limit|[^0-9]429[^0-9]|usage limit hard|try again later", t, re.I):
        return "error_capacity"
    if re.search(
        r"ECONNRESET|connection failed|connection error|connect timed out|request timed out|"
        r"stream timed out|network timeout|TLS handshake timeout|websocket.*timeout",
        t,
        re.I,
    ):
        return "error_connection"
    # Codex ready chrome
    if "›" in t:
        if re.search(r"bag empty|standing by|turn end|Turn completed|ready-to-merge", t, re.I):
            return "done_idle"
        return "idle_prompt"
    # Grok-style prompt box
    if re.search(r"Grok|always-approve|Shift\+Tab", t) and re.search(r"Turn completed|Idle until|Board empty|bag empty|❯", t, re.I):
        if re.search(r"Turn completed|Idle until|Board empty|bag empty|actionable: 0", t, re.I):
            return "done_idle"
        return "idle_prompt"
    if re.search(r"❯\s*$|╰─.*Grok|codex ›|^\s*›\s*$", t, re.M):
        return "idle_prompt"
    # opencode TUI — status bar markers like "OpenCode Zen" / "Build ·" / "ctrl+p commands"
    if re.search(r"OpenCode Zen|Build auto|Build ·|ctrl\+p commands", t):
        last_lines = [x for x in (t.splitlines() or []) if x.strip()]
        bottom = "\n".join(last_lines[-6:]) if last_lines else ""
        if re.search(r"Ask anything\.\.\.", bottom):
            return "idle_prompt"
        if re.search(r"⬝|esc interrupt", bottom):
            return "running"
        return "idle_prompt"
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

# Default every_n_loops (Head sweep multiplier) by posture × role. Each is
# overridable per head via executive_cadence.every_n_loops in fleet.json.
# sweep_interval = every_n_loops × mind_loop.interval_sec. Dormant pauses sweeps.
HEAD_CADENCE_DEFAULTS = {
    "growth": {"head-cto": 6, "head-cxo": 12, "head-ceo": 36},   # @5m: 30m / 1h / 3h
    "standby": {"head-cto": 18, "head-cxo": 36, "head-ceo": 72},  # @5m: 1.5h / 3h / 6h
    # dormant: no table — sweeps paused
}


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


def head_cadence_every_n_loops(posture_mode: str, head_key: str, override: Any = None) -> Optional[int]:
    """Head sweep multiplier (every_n_loops).

    Order: explicit executive_cadence.every_n_loops wins; else the posture×role
    default table; else None (caller falls back conservatively / dormant pauses).
    """
    if override is not None:
        try:
            return max(1, int(override))
        except (TypeError, ValueError):
            pass
    table = HEAD_CADENCE_DEFAULTS.get(posture_mode)
    if not isinstance(table, dict):
        return None
    n = table.get(head_key)
    if n is None:
        return None
    try:
        return max(1, int(n))
    except (TypeError, ValueError):
        return None


def head_sweep_interval_sec(fleet: dict, posture_mode: str, head_key: str, override: Any = None) -> int:
    """Seconds between Head sweeps: every_n_loops × mind_loop.interval_sec.

    every_n_loops comes from executive_cadence.every_n_loops when set, else the
    posture×role default table. Unknown head / no default → loop tick (conservative).
    """
    loop = mind_loop_interval_sec(fleet)
    n = head_cadence_every_n_loops(posture_mode, head_key, override)
    if n is None:
        return loop
    return max(n * loop, loop)


def resolve_posture(fleet: dict, baseline: dict) -> tuple:
    """Return (mode, suppress_starvation, pause_executive_sweeps, posture_out_dict).

    Hands: standby+dormant suppress starvation refill (quiet Hands is success).
    Heads: only dormant pauses default executive cadence; standby allows
    stewardship sweeps (not expansion). Cadence spacing = every_n_loops ×
    mind_loop.interval_sec; every_n_loops configurable per head, else posture×role
    default. See fleet-posture.md.
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
        "hand1_class": (h1 or {}).get("pane_class"),
        "hand2_class": (h2 or {}).get("pane_class"),
        "operator_open": (out.get("operator") or {}).get("open_count", 0),
        "steward_armed": (out.get("steward") or {}).get("armed"),
        "steward_tripped": (out.get("steward") or {}).get("tripped"),
        "map_focus": (fleet.get("focus") or {}).get("chapter")
        or (fleet.get("focus") or {}).get("primary_goal"),
    }
    for hkey, hdata in (out.get("heads") or {}).items():
        sk = hkey.replace("-", "_")
        fp["%s_due" % sk] = hdata.get("sweep_due")
    for stale in list(fp.keys()):
        if re.match(r"^head_(ceo|cto|cxo)_last_(handle|completed)$", stale):
            del fp[stale]
    return fp


def quiet_hint_from(fp: dict, prev: dict, signals: list, steward: dict) -> bool:
    keys = (
        "hand1_open",
        "hand2_open",
        "next_handle_h1",
        "next_handle_h2",
        "swarm_head",
        "hand1_class",
        "hand2_class",
        "operator_open",
        "steward_tripped",
        "head_ceo_due",
        "head_cto_due",
        "head_cxo_due",
    )
    hard = [s for s in signals if not s.startswith("starvation_candidate")]
    fp_cmp = {k: fp.get(k) for k in keys}
    prev_cmp = {k: prev.get(k) for k in keys}
    return fp_cmp == prev_cmp and not hard and not steward.get("tripped")


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
        lines.append(
            "  %s: bag=%s next=%s class=%s%s target=%s"
            % (
                name,
                h.get("actionable"),
                h.get("next_handle"),
                h.get("pane_class"),
                stall_lab,
                h.get("tmux_target"),
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
            "  %s: class=%s sweep=%s last=%s%s target=%s"
            % (
                name,
                hd.get("pane_class"),
                sweep_lab,
                (hd.get("sweep_last_completed") or "never")[:19],
                extra,
                hd.get("tmux_target"),
            )
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fleet cheap sensors snapshot (Python 3.9+; macOS/Linux)")
    ap.add_argument("--project", "-p", required=True, help="Fleet project root")
    ap.add_argument("--fleet", "-f", default=None, help="Path to fleet.json (default: PROJECT/.vivi/fleet.json)")
    ap.add_argument("--json", action="store_true", default=True, help="JSON output (default)")
    ap.add_argument("--text", action="store_true", help="Human text summary instead of JSON")
    ap.add_argument("--no-watch", action="store_true", help="Skip mailspace watch --once")
    ap.add_argument("--tail", type=int, default=16, help="tmux capture lines per pane")
    ap.add_argument("--cursor-file", default=None, help="watch cursor path (default: .vivi/mind-watch.cursor)")
    args = ap.parse_args()

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(json.dumps({"error": "project not a directory: %s" % project}), file=sys.stderr)
        return 1

    fleet_path = Path(args.fleet).expanduser().resolve() if args.fleet else project / ".vivi" / "fleet.json"
    fleet = load_json(fleet_path)
    baseline_path = project / ".vivi" / "mind-baseline.json"
    baseline = load_json(baseline_path)
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
    out["mind"] = {
        "identity": mind_inbox,
        "inbox_unread": mind_row.get("inbox_unread", 0),
        "from_operator": op_to_mind,
        "from_operator_count": len(op_to_mind),
    }

    # --- fleet posture (continuity vs sleep) ---
    (
        posture_mode,
        posture_suppresses_starvation,
        posture_pauses_executive_sweeps,
        posture_out,
    ) = resolve_posture(fleet, baseline)
    out["fleet_posture"] = posture_out

    # --- hands panes + bag ---
    pane_classes = {}  # type: Dict[str, str]
    # stall-risk: track per-hand pane-tail stability across cycles so a frozen
    # pane with open assigned work surfaces as a signal even when the pane
    # classifier (a brittle string matcher) mis-reads it as idle. State rides in
    # baseline.hand_progress, persisted by fleet-baseline.py bump.
    _php = baseline.get("hand_progress")
    prev_hand_progress = _php if isinstance(_php, dict) else {}
    stall_floor = int(fleet.get("stall_risk_cycles_floor") or 3)
    hand_progress = {}  # type: Dict[str, Dict[str, Any]]
    if tmux and (Path(tmux).is_file() or shutil.which(tmux)):
        tmux_bin = tmux if Path(tmux).is_file() else (shutil.which(tmux) or tmux)
    else:
        tmux_bin = shutil.which("tmux") or ""
    if not tmux_bin:
        partial = True
        out["signals"].append("tmux_missing")

    for name, h in hands.items():
        if not isinstance(h, dict):
            continue
        mid = h.get("mail_identity") or name
        target = h.get("tmux_target") or ("%s:1.1" % (h.get("tmux_session") or name))
        session = target.split(":")[0]
        cwd = h.get("cwd") or str(project)
        agent = h.get("agent") or "unknown"
        row = out["identities"].get(mid) or {}
        open_tasks = list_open_handles(vivi, str(project), mid, "task") if vivi else []
        open_needs = list_open_handles(vivi, str(project), mid, "need") if vivi else []
        bag_open = (row.get("tasks_open") or len(open_tasks)) + (row.get("needs_open") or len(open_needs))

        sess_ok = False
        tail = ""
        if tmux_bin:
            rc, _ = run([tmux_bin, "has-session", "-t", session], timeout=5)
            sess_ok = rc == 0
            if sess_ok:
                rc, tail = run(
                    [tmux_bin, "capture-pane", "-t", target, "-p", "-S", "-%d" % args.tail],
                    timeout=5,
                )
                if rc != 0:
                    tail = ""
                    partial = True

        pclass = classify_pane(tail, sess_ok)
        pane_classes[name] = pclass
        next_handle = open_tasks[0]["handle"] if open_tasks else (open_needs[0]["handle"] if open_needs else None)

        if pclass in ("error_capacity", "error_connection", "down", "trust_prompt"):
            out["signals"].append(f"pane_{name}_{pclass}")
        packet = h.get("packet") if isinstance(h.get("packet"), dict) else {}
        pkt_state = str(packet.get("state") or "").lower()
        paused_pkt = pkt_state.startswith("paused") or pkt_state in ("hold", "operational_pause")
        hand_paused = hand_is_paused(baseline, name)
        if (
            bag_open
            and pclass in ("idle_prompt", "done_idle", "unknown")
            and not hand_paused
            and not paused_pkt
        ):
            out["signals"].append(f"wake_candidate_{name}")
        # Starvation is a candidate only — suppress when fleet/baseline marks intentional pause
        if (
            bag_open == 0
            and pclass in ("idle_prompt", "done_idle")
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
        prev_hash = prev_hp.get("pane_tail_hash")
        if pane_tail_hash and prev_hash and pane_tail_hash == prev_hash:
            cycles_unchanged = int(prev_hp.get("cycles_unchanged") or 0) + 1
        else:
            cycles_unchanged = 0
        hand_progress[name] = {
            "pane_tail_hash": pane_tail_hash,
            "cycles_unchanged": cycles_unchanged,
            "has_open_work": bool(bag_open),
            "pane_class": pclass,
        }
        if (
            bag_open
            and cycles_unchanged >= stall_floor
            and pclass != "running"
            and not hand_paused
            and not paused_pkt
        ):
            out["signals"].append(f"stall_risk_{name}")

        out["hands"][name] = {
            "mail_identity": mid,
            "tmux_target": target,
            "tmux_session": session,
            "agent": agent,
            "cwd": cwd,
            "tasks_open": row.get("tasks_open", len(open_tasks)),
            "needs_open": row.get("needs_open", len(open_needs)),
            "actionable": row.get("actionable", bag_open),
            "open_tasks": open_tasks,
            "open_needs": open_needs,
            "next_handle": next_handle,
            "pane_class": pclass,
            "pane_tail": pane_tail_text,
            "pane_tail_hash": pane_tail_hash,
            "cycles_unchanged": cycles_unchanged,
            "min_seconds_between_wakes": h.get("min_seconds_between_wakes", 180),
            "merges_to_main": h.get("merges_to_main", False),
            "packet_state": packet.get("state"),
            "operational_pause": hand_paused or paused_pkt,
        }

        # git for main hand (walk up from cwd; container fleets scan children / git.main_cwd)
        if h.get("merges_to_main") or name == fleet.get("default_hand"):
            out["git"]["main"] = git_tip(Path(cwd), fleet)

    out["hand_progress"] = hand_progress

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
    # Interval = every_n_loops × mind_loop.interval_sec (default 5m tick).
    # every_n_loops: executive_cadence.every_n_loops when set, else posture×role default.
    # Due when that interval elapsed since last completion mail AND pane not mid-pass.
    # Completion: new mail from head identity/legacy_aliases in head_report_inbox.
    # Durable last-report on baseline head-*; opt-in: executive_cadence.enabled=true.
    # interval_sec / min_seconds_between_sweeps are ignored (legacy) — set every_n_loops.
    now_dt = datetime.now(timezone.utc)
    loop_sec = int(posture_out.get("mind_loop_interval_sec") or mind_loop_interval_sec(fleet))
    for key in ("head-ceo", "head-cto", "head-cxo"):
        block = fleet.get(key)
        if not isinstance(block, dict):
            block = (fleet.get("heads") or {}).get(key)
        if not isinstance(block, dict):
            continue
        target = block.get("tmux_target") or f"{block.get('tmux_session') or key}:1.1"
        session = target.split(":")[0]
        sess_ok = False
        tail = ""
        if tmux_bin:
            rc, _ = run([tmux_bin, "has-session", "-t", session], timeout=5)
            sess_ok = rc == 0
            if sess_ok:
                _, tail = run(
                    [tmux_bin, "capture-pane", "-t", target, "-p", "-S", "-%d" % min(args.tail, 12)],
                    timeout=5,
                )
        pclass = classify_pane(tail, sess_ok)
        pane_classes[key] = pclass

        cad = block.get("executive_cadence") if isinstance(block.get("executive_cadence"), dict) else {}
        sweep_enabled = bool(cad.get("enabled", False))
        # every_n_loops is primary (configurable via executive_cadence.every_n_loops);
        # sweep_interval = every_n_loops × mind_loop.interval_sec.
        every_n = head_cadence_every_n_loops(posture_mode, key, cad.get("every_n_loops"))
        sweep_interval = head_sweep_interval_sec(fleet, posture_mode, key, cad.get("every_n_loops"))
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
            and pclass != "running"
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
        if pclass in ("error_capacity", "error_connection", "down", "trust_prompt"):
            out["signals"].append("pane_%s_%s" % (key, pclass))

        out["heads"][key] = {
            "tmux_target": target,
            "pane_class": pclass,
            "pane_tail": "\n".join((tail or "").splitlines()[-8:]),
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

    # steward block from fleet + baseline + optional pane
    st_cfg = fleet.get("steward") or {}
    st_base = baseline.get("steward") or {}
    st_target = st_cfg.get("tmux_target") or ("%s:1.1" % (st_cfg.get("tmux_session") or "steward"))
    st_session = st_target.split(":")[0]
    st_sess_ok = False
    st_tail = ""
    if tmux_bin:
        rc, _ = run([tmux_bin, "has-session", "-t", st_session], timeout=5)
        st_sess_ok = rc == 0
        if st_sess_ok:
            _, st_tail = run(
                [tmux_bin, "capture-pane", "-t", st_target, "-p", "-S", "-8"],
                timeout=5,
            )
    st_class = classify_pane(st_tail, st_sess_ok)
    pane_classes["steward"] = st_class
    last_ok = (baseline.get("mind_loop") or {}).get("last_successful_cycle_at") or st_base.get(
        "last_rearm_at"
    )
    out["steward"] = {
        # Default OFF — match steward.sh and process law (opt-in dead-man).
        "enabled": st_cfg.get("enabled", False),
        "armed": bool(st_base.get("armed")),
        "tripped": bool(st_base.get("tripped")),
        "tmux_target": st_target,
        "pane_class": st_class,
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
    out["pane_classes"] = pane_classes
    out["quiet_hint"] = quiet_hint_from(fp, prev, out["signals"], out["steward"])
    out["baseline_last_cycle"] = baseline.get("last_cycle")
    out["baseline_mind_mode"] = baseline.get("mind_mode")
    out["partial"] = partial
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
