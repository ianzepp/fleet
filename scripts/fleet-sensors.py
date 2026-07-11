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
import json
import re
import shutil
import sys
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


def classify_pane(text: str, session_exists: bool) -> str:
    """running|idle_prompt|done_idle|trust_prompt|error_capacity|error_connection|down|unknown"""
    if not session_exists:
        return "down"
    t = text or ""
    if re.search(r"Working \(|esc to interrupt|Waiting for response|Responding…|Responding\.\.\.|Thinking…", t, re.I):
        return "running"
    if re.search(r"Yes, continue|Do you trust|trust this workspace|No, quit|Press enter to continue", t, re.I):
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


def list_mail_from_operator(
    vivi: str, project: str, mind_identity: str, operator_identity: str, limit: int = 20
) -> List[Dict[str, str]]:
    """Cheap scan of mind@ for mail FROM operator@ (operator feedback / decisions).

    vivi mail list lines look like:
      <handle>  <from@mailspace>  <subject…>
    """
    cmd = [vivi, "mail", "list", "--for", mind_identity, "--project", project]
    rc, out = run(cmd, timeout=20)
    if rc != 0 or not out.strip():
        return []
    op_token = (operator_identity or "operator").lower()
    # match operator@… or bare operator as local-part
    op_pat = re.compile(
        r"^([a-f0-9]{6,})\s+(\S*operator\S*)\s+(.*)$",
        re.I,
    )
    found = []  # type: List[Dict[str, str]]
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("handle"):
            continue
        m = op_pat.match(line)
        if not m:
            # fallback: handle + from column contains operator
            parts = line.split(None, 2)
            if len(parts) < 3 or not re.match(r"^[a-f0-9]{6,}$", parts[0]):
                continue
            fr = parts[1].lower()
            if "operator" not in fr and not fr.startswith(op_token + "@"):
                continue
            found.append({"handle": parts[0], "from": parts[1], "subject": parts[2].strip()})
            continue
        fr = m.group(2).lower()
        if op_token not in fr and not fr.startswith("operator@"):
            continue
        found.append(
            {
                "handle": m.group(1),
                "from": m.group(2),
                "subject": m.group(3).strip(),
            }
        )
        if len(found) >= limit:
            break
    return found


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
    if rc2 == 0:
        first = st.splitlines()[0] if st.strip() else ""
        dirty = any(ln.strip() and not ln.startswith("##") for ln in st.splitlines())
        m = re.search(r"ahead (\d+)", first)
        if m:
            ahead = int(m.group(1))
    return {
        "cwd": str(cwd),
        "sha": sha,
        "subject": subj,
        "dirty": dirty,
        "status_sb": st.strip().splitlines()[0] if st.strip() else "",
        "ahead": ahead,
    }


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
    tooling = fleet.get("tooling") or {}

    vivi = which("vivi", tooling, "vivi") or which("vivi")
    tmux = which("tmux") or which("tmux")  # PATH only — no macOS-only default
    if not tmux:
        # last-ditch common locations (mac + linux)
        for cand in (
            "/opt/homebrew/bin/tmux",
            "/usr/local/bin/tmux",
            "/usr/bin/tmux",
            "/home/linuxbrew/.linuxbrew/bin/tmux",
        ):
            if Path(cand).is_file():
                tmux = cand
                break
    if not tmux:
        tmux = "tmux"
    mind_inbox = fleet.get("mind_inbox") or "mind"
    operator_inbox = fleet.get("operator_inbox") or "operator"
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
    posture_block = fleet.get("fleet_posture") if isinstance(fleet.get("fleet_posture"), dict) else {}
    if not posture_block and isinstance(baseline.get("fleet_posture"), dict):
        posture_block = baseline.get("fleet_posture") or {}
    posture_mode = str(posture_block.get("mode") or "growth").lower()
    if posture_mode in ("campaign", "active"):
        posture_mode = "growth"
    if posture_mode in ("on_call", "on-call"):
        posture_mode = "standby"
    out["fleet_posture"] = {
        "mode": posture_mode,
        "reason": posture_block.get("reason"),
    }
    # standby/dormant: empty bags are expected — no starvation noise
    posture_suppresses_starvation = posture_mode in ("standby", "dormant")

    # --- hands panes + bag ---
    pane_classes = {}  # type: Dict[str, str]
    tmux_bin = tmux if (tmux and (Path(tmux).exists() or shutil.which(tmux))) else (shutil.which("tmux") or "")
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
        if bag_open and pclass in ("idle_prompt", "done_idle", "unknown"):
            out["signals"].append(f"wake_candidate_{name}")
        # Starvation is a candidate only — suppress when fleet/baseline marks intentional pause
        packet = h.get("packet") if isinstance(h.get("packet"), dict) else {}
        pkt_state = str(packet.get("state") or "").lower()
        paused_pkt = pkt_state.startswith("paused") or pkt_state in ("hold", "operational_pause")
        op_pauses = baseline.get("operational_pauses") or []
        hand_paused = False
        if isinstance(op_pauses, list):
            for p in op_pauses:
                if isinstance(p, dict) and p.get("hand") == name:
                    hand_paused = True
                    break
        if (
            bag_open == 0
            and pclass in ("idle_prompt", "done_idle")
            and not paused_pkt
            and not hand_paused
            and not posture_suppresses_starvation
        ):
            out["signals"].append(f"starvation_candidate_{name}")

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
            "pane_tail": "\n".join((tail or "").splitlines()[-args.tail :]),
            "wake_enabled": h.get("wake_enabled", True),
            "min_seconds_between_wakes": h.get("min_seconds_between_wakes", 180),
            "merges_to_main": h.get("merges_to_main", False),
            "packet_state": packet.get("state"),
            "operational_pause": hand_paused or paused_pkt,
        }

        # git for main hand (walk up from cwd; container fleets scan children / git.main_cwd)
        if h.get("merges_to_main") or name == fleet.get("default_hand"):
            out["git"]["main"] = git_tip(Path(cwd), fleet)

    # heads (optional pane scan)
    for key in ("head-ceo", "head-cto", "head-cxo"):
        block = fleet.get(key)
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
        out["heads"][key] = {
            "tmux_target": target,
            "pane_class": pclass,
            "pane_tail": "\n".join((tail or "").splitlines()[-8:]),
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
        "enabled": st_cfg.get("enabled", True),
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

    # fingerprint for quiet detection
    h1 = out["hands"].get(fleet.get("default_hand") or "hand-1") or next(iter(out["hands"].values()), {})
    h2 = out["hands"].get("hand-2") or {}
    git_main = out.get("git", {}).get("main") or {}
    fp = {
        "hand1_open": (h1 or {}).get("actionable") or (h1 or {}).get("tasks_open") or 0,
        "hand2_open": (h2 or {}).get("actionable") or (h2 or {}).get("tasks_open") or 0,
        "next_handle_h1": (h1 or {}).get("next_handle"),
        "next_handle_h2": (h2 or {}).get("next_handle"),
        "swarm_head": (git_main.get("sha") or "")[:12] or None,
        "hand1_class": (h1 or {}).get("pane_class"),
        "hand2_class": (h2 or {}).get("pane_class"),
        "operator_open": out["operator"].get("open_count", 0),
        "steward_armed": out["steward"].get("armed"),
        "steward_tripped": out["steward"].get("tripped"),
        "map_focus": (fleet.get("focus") or {}).get("chapter") or (fleet.get("focus") or {}).get("primary_goal"),
    }
    out["fingerprint"] = fp
    out["pane_classes"] = pane_classes

    prev = baseline.get("last_actionable_fingerprint") or {}
    if not isinstance(prev, dict):
        # legacy gatherer baselines stored a string fingerprint
        prev = {}
    # quiet if fingerprint equal and no hard signals
    hard = [s for s in out["signals"] if not s.startswith("starvation_candidate")]
    # starvation when bag empty + idle + map still has chapter? Mind decides map; we only flag candidates
    fp_cmp = {k: fp.get(k) for k in ("hand1_open", "hand2_open", "next_handle_h1", "next_handle_h2", "swarm_head", "hand1_class", "hand2_class", "operator_open", "steward_tripped")}
    prev_cmp = {k: prev.get(k) for k in fp_cmp}
    out["quiet_hint"] = fp_cmp == prev_cmp and not hard and not out["steward"].get("tripped")
    out["baseline_last_cycle"] = baseline.get("last_cycle")
    out["baseline_mind_mode"] = baseline.get("mind_mode")
    out["partial"] = partial
    out["ok"] = not partial or bool(out["hands"])

    if args.text:
        lines = [
            "fleet %s @ %s" % (out["fleet_id"], out["at"]),
            "focus: %s" % fp.get("map_focus"),
            "posture: %s" % ((out.get("fleet_posture") or {}).get("mode") or "growth"),
            "git: %s dirty=%s" % (fp.get("swarm_head"), git_main.get("dirty")),
            "operator_open=%s operator_to_mind=%s steward_armed=%s tripped=%s"
            % (
                out["operator"].get("open_count"),
                out["operator"].get("to_mind_count", 0),
                out["steward"].get("armed"),
                out["steward"].get("tripped"),
            ),
            "quiet_hint=%s signals=%s" % (out["quiet_hint"], out["signals"]),
        ]
        for om in (out.get("operator") or {}).get("to_mind") or []:
            lines.append(
                "  op→mind %s: %s"
                % (om.get("handle"), (om.get("subject") or "")[:80])
            )
        for name, h in out["hands"].items():
            lines.append(
                "  %s: bag=%s next=%s class=%s target=%s"
                % (
                    name,
                    h.get("actionable"),
                    h.get("next_handle"),
                    h.get("pane_class"),
                    h.get("tmux_target"),
                )
            )
        print("\n".join(lines))
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
