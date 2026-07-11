#!/bin/bash
# Fleet steward (dead man): fleet-local completed-cycle watchdog.
#
# Mind rearms after every successful FLEET_CYCLE. If rearm stops while armed,
# steward trips: board operator@ + optional external email + hold baseline.
#
# Usage:
#   PROJECT=/path/to/fleet path/to/steward.sh arm|rearm|disarm|status|check|clear|loop|trip
#   steward.sh arm --project /path/to/fleet
#
# Exit: 0 ok · 1 tripped (check/loop) · 2 config/error · 3 inactive/disarmed
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}:$HOME/.cargo/bin:$HOME/.local/bin"

PROJECT="${PROJECT:-}"
CMD="${1:-}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --project=*) PROJECT="${1#*=}"; shift ;;
    -h|--help) CMD=help; shift ;;
    *) break ;;
  esac
done

if [[ -z "$PROJECT" ]]; then
  if [[ -f .vivi/fleet.json || -f .vivi/mind-baseline.json ]]; then
    PROJECT="$(pwd)"
  else
    echo "ERROR: set PROJECT or --project <root>" >&2
    exit 2
  fi
fi
PROJECT="$(cd "$PROJECT" && pwd)"
FLEET="${FLEET:-$PROJECT/.vivi/fleet.json}"
BASELINE="${BASELINE:-$PROJECT/.vivi/mind-baseline.json}"
VIVI_DIR="$PROJECT/.vivi"
REARM_TOUCH="$VIVI_DIR/steward.rearm"
LOG="${STEWARD_LOG:-$VIVI_DIR/steward.log}"
TMUX_BIN="${TMUX_BIN:-$(command -v tmux 2>/dev/null || echo /opt/homebrew/bin/tmux)}"
VIVI_BIN="${VIVI_BIN:-$(command -v vivi 2>/dev/null || true)}"
if [[ -z "${VIVI_BIN}" || ! -x "${VIVI_BIN}" ]]; then
  for c in /opt/homebrew/bin/vivi "$HOME/.cargo/bin/vivi"; do
    [[ -x "$c" ]] && VIVI_BIN="$c" && break
  done
fi
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 2>/dev/null || echo /usr/bin/python3)}"
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG" >&2; }

die() { log "ERROR: $*"; exit 2; }

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 3
}

[[ -d "$VIVI_DIR" ]] || mkdir -p "$VIVI_DIR"
[[ -f "$BASELINE" ]] || echo '{}' >"$BASELINE"
touch "$LOG"

# --- JSON helpers via python ---
py() {
  "$PYTHON_BIN" - "$PROJECT" "$FLEET" "$BASELINE" "$@" <<'PY'
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

project, fleet_path, baseline_path = sys.argv[1], sys.argv[2], sys.argv[3]
op = sys.argv[4]
args = sys.argv[5:]

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def load_json(path, default=None):
    p = Path(path)
    if not p.is_file():
        return {} if default is None else default
    try:
        return json.loads(p.read_text())
    except Exception:
        return {} if default is None else default

def save_baseline(b):
    Path(baseline_path).write_text(json.dumps(b, indent=2) + "\n")

def fleet_steward():
    f = load_json(fleet_path, {})
    s = f.get("steward") or {}
    fleet_id = f.get("fleet_id") or f.get("mailspace") or Path(project).name
    # Steward pane: prefer explicit tmux_target; support session_per_fleet
    sess = s.get("tmux_session") or "steward"
    win = s.get("tmux_window") or "steward"
    target = s.get("tmux_target")
    if not target:
        # legacy: session named steward → steward:1.1
        # session_per_fleet: fleet session + steward window → mgs:steward.1
        layout = f.get("tmux_layout") or s.get("tmux_layout") or "legacy"
        if layout == "session_per_fleet" or (sess == fleet_id and win):
            target = f"{sess}:{win}.1"
        else:
            target = f"{sess}:1.1"
    # Hands: list tmux_target for soft-hold (never hardcode session==role)
    hand_targets = []
    hands = f.get("hands") or f.get("hands") or {}
    for name, h in hands.items():
        if not isinstance(h, dict):
            continue
        ht = h.get("tmux_target")
        if not ht:
            hs = h.get("tmux_session") or name
            hw = h.get("tmux_window") or name
            layout = f.get("tmux_layout") or "legacy"
            if layout == "session_per_fleet":
                ht = f"{hs}:{hw}.1"
            else:
                ht = f"{hs}:1.1"
        hand_targets.append({"name": name, "tmux_target": ht})
    return {
        "enabled": s.get("enabled", True),
        "fleet_id": fleet_id,
        "tmux_session": sess,
        "tmux_window": win,
        "tmux_target": target,
        "hand_targets": hand_targets,
        "grace_sec": int(s.get("grace_sec", 900)),
        "poll_sec": int(s.get("poll_sec", 60)),
        "mode": s.get("mode", "hold"),
        "notify": {
            "operator_board": (s.get("notify") or {}).get("operator_board", True),
            "external_email": (s.get("notify") or {}).get("external_email", False),
            "account": (s.get("notify") or {}).get("account"),
            "to": (s.get("notify") or {}).get("to") or [],
            "dedupe_hours": int((s.get("notify") or {}).get("dedupe_hours", 6)),
            "preauthorized_exec_send": bool((s.get("notify") or {}).get("preauthorized_exec_send", False)),
        },
        "fleet_name": f.get("mailspace") or fleet_id or Path(project).name,
        "interval_sec": int((f.get("mind_loop") or {}).get("interval_sec") or 300),
    }

def ensure_steward_block(b):
    st = b.get("steward")
    if not isinstance(st, dict):
        st = {}
        b["steward"] = st
    return st

def parse_iso(s):
    if not s:
        return None
    try:
        s = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None

def age_sec(iso):
    dt = parse_iso(iso)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()

cfg = fleet_steward()
b = load_json(baseline_path, {})
st = ensure_steward_block(b)
ml = b.get("mind_loop") if isinstance(b.get("mind_loop"), dict) else {}
if not isinstance(b.get("mind_loop"), dict):
    b["mind_loop"] = ml

if op == "cfg":
    print(json.dumps(cfg))
    sys.exit(0)

if op == "status":
    last = ml.get("last_successful_cycle_at") or st.get("last_rearm_at")
    age = age_sec(last)
    print(json.dumps({
        "project": project,
        "enabled": cfg["enabled"],
        "armed": bool(st.get("armed")),
        "tripped": bool(st.get("tripped")),
        "grace_sec": cfg["grace_sec"],
        "poll_sec": cfg["poll_sec"],
        "mode": cfg["mode"],
        "last_successful_cycle_at": last,
        "age_sec": None if age is None else int(age),
        "armed_at": st.get("armed_at"),
        "last_rearm_at": st.get("last_rearm_at"),
        "tripped_at": st.get("tripped_at"),
        "fleet_id": cfg.get("fleet_id"),
        "tmux_session": cfg["tmux_session"],
        "tmux_target": cfg.get("tmux_target"),
        "hand_targets": cfg.get("hand_targets") or [],
        "notify_external": cfg["notify"]["external_email"],
    }, indent=2))
    sys.exit(0)

if op == "arm":
    now = now_iso()
    st["armed"] = True
    st["armed_at"] = now
    st["tripped"] = False
    st.pop("tripped_at", None)
    st.pop("last_trip_reason", None)
    st["last_rearm_at"] = now
    # Grace starts from arm — do not inherit a stale pre-arm tick
    ml["last_successful_cycle_at"] = now
    ml["last_cycle_ok"] = True
    if ml.get("state") in (None, "wound_up", "stopping", "dead_man_tripped"):
        ml["state"] = "running"
    save_baseline(b)
    print("armed")
    sys.exit(0)

if op == "rearm":
    now = now_iso()
    st["last_rearm_at"] = now
    ml["last_successful_cycle_at"] = now
    ml["last_cycle_ok"] = True
    # rearm does not clear trip; use clear for that
    save_baseline(b)
    print(now)
    sys.exit(0)

if op == "disarm":
    st["armed"] = False
    st["disarmed_at"] = now_iso()
    st["tripped"] = False
    save_baseline(b)
    print("disarmed")
    sys.exit(0)

if op == "clear":
    st["tripped"] = False
    st.pop("tripped_at", None)
    st.pop("last_trip_reason", None)
    st["last_rearm_at"] = now_iso()
    ml["last_successful_cycle_at"] = now_iso()
    if ml.get("state") == "dead_man_tripped":
        ml["state"] = "running"
    save_baseline(b)
    print("cleared")
    sys.exit(0)

if op == "should_trip":
    if not cfg["enabled"]:
        print("inactive"); sys.exit(3)
    if not st.get("armed"):
        print("disarmed"); sys.exit(3)
    if st.get("tripped"):
        print("already_tripped"); sys.exit(0)
    last = ml.get("last_successful_cycle_at") or st.get("last_rearm_at")
    age = age_sec(last)
    if age is None:
        # never tickled — use armed_at
        age = age_sec(st.get("armed_at")) or 0
    grace = cfg["grace_sec"]
    if age > grace:
        print(f"trip age={int(age)} grace={grace}")
        sys.exit(1)
    print(f"ok age={int(age)} grace={grace}")
    sys.exit(0)

if op == "mark_tripped":
    reason = args[0] if args else "missed_successful_cycle"
    st["tripped"] = True
    st["tripped_at"] = now_iso()
    st["last_trip_reason"] = reason
    ml["state"] = "dead_man_tripped"
    b["mind_loop"] = ml
    save_baseline(b)
    print(st["tripped_at"])
    sys.exit(0)

if op == "mark_external":
    ok = args[0] if args else "ok"
    if ok == "ok":
        st["last_external_notify_at"] = now_iso()
        st.pop("last_external_error", None)
    else:
        st["last_external_error"] = " ".join(args[1:])[:500]
    save_baseline(b)
    print("ok")
    sys.exit(0)

if op == "notify_meta":
    # print shell-friendly meta for trip notify
    last = ml.get("last_successful_cycle_at") or st.get("last_rearm_at") or "unknown"
    age = age_sec(last)
    dedupe_h = cfg["notify"]["dedupe_hours"]
    last_ext = st.get("last_external_notify_at")
    skip_ext = False
    if last_ext:
        a = age_sec(last_ext)
        if a is not None and a < dedupe_h * 3600:
            skip_ext = True
    print(json.dumps({
        "fleet": cfg.get("fleet_name") or cfg.get("fleet_id"),
        "fleet": cfg.get("fleet_name") or cfg.get("fleet_id"),  # legacy key for callers
        "project": project,
        "last_successful_cycle_at": last,
        "age_sec": None if age is None else int(age),
        "grace_sec": cfg["grace_sec"],
        "mode": cfg["mode"],
        "operator_board": cfg["notify"]["operator_board"],
        "external_email": cfg["notify"]["external_email"],
        "account": cfg["notify"]["account"],
        "to": cfg["notify"]["to"],
        "preauthorized": cfg["notify"]["preauthorized_exec_send"],
        "skip_external_dedupe": skip_ext,
        "tripped_at": st.get("tripped_at"),
        "reason": st.get("last_trip_reason") or "missed_successful_cycle",
        "hand_targets": cfg.get("hand_targets") or [],
        "tmux_target": cfg.get("tmux_target"),
    }))
    sys.exit(0)

if op == "hand_targets":
    print(json.dumps(cfg.get("hand_targets") or []))
    sys.exit(0)

if op == "tmux_target":
    print(cfg.get("tmux_target") or "steward:1.1")
    sys.exit(0)

print("unknown op", op, file=sys.stderr)
sys.exit(2)
PY
}

cmd_status() { py status; }

cmd_arm_state() { py arm; touch "$REARM_TOUCH"; }

cmd_rearm() {
  py rearm
  touch "$REARM_TOUCH"
  log "rearm ok"
}

cmd_disarm_state() { py disarm; }

cmd_clear() { py clear; touch "$REARM_TOUCH"; log "trip cleared"; }

# Steward pane target from fleet.json (supports legacy steward:1.1 and mgs:steward.1)
steward_tmux_target() {
  py tmux_target 2>/dev/null || echo "steward:1.1"
}

# Session name is portion before first colon of target
tmux_session_from_target() {
  local t=$1
  echo "${t%%:*}"
}

# Window name for session_per_fleet create (between : and . if present)
tmux_window_from_target() {
  local t=$1 rest
  rest="${t#*:}"
  echo "${rest%%.*}"
}

ensure_tmux_session() {
  local target sess win
  target="$(steward_tmux_target)"
  sess="$(tmux_session_from_target "$target")"
  win="$(tmux_window_from_target "$target")"
  [[ -n "$win" ]] || win="steward"
  if ! "$TMUX_BIN" has-session -t "$sess" 2>/dev/null; then
    # Named first window when using session_per_fleet (win != numeric default)
    if [[ "$win" =~ ^[0-9]+$ ]]; then
      "$TMUX_BIN" new-session -d -s "$sess" -c "$PROJECT"
    else
      "$TMUX_BIN" new-session -d -s "$sess" -n "$win" -c "$PROJECT"
    fi
    log "created tmux session $sess window=$win"
  else
    # Ensure named steward window exists under fleet session
    if [[ ! "$win" =~ ^[0-9]+$ ]]; then
      if ! "$TMUX_BIN" list-windows -t "$sess" -F '#{window_name}' 2>/dev/null | grep -qx "$win"; then
        "$TMUX_BIN" new-window -t "$sess" -n "$win" -c "$PROJECT"
        log "created window $sess:$win"
      fi
    fi
  fi
  "$TMUX_BIN" send-keys -t "$target" C-c 2>/dev/null || true
}

cmd_arm() {
  local target sess poll
  [[ -f "$FLEET" ]] || die "missing fleet.json: $FLEET"
  if ! py cfg | "$PYTHON_BIN" -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("enabled",True) else 1)'; then
    log "steward disabled in fleet.json"
    exit 3
  fi
  cmd_arm_state
  ensure_tmux_session
  target="$(steward_tmux_target)"
  sess="$(tmux_session_from_target "$target")"
  poll="$(py cfg | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["poll_sec"])')"
  "$TMUX_BIN" send-keys -t "$target" C-c 2>/dev/null || true
  sleep 0.2
  "$TMUX_BIN" send-keys -t "$target" -l "cd $(printf %q "$PROJECT") && STEWARD_LOG=$(printf %q "$LOG") $(printf %q "$SELF") loop --project $(printf %q "$PROJECT") 2>&1 | tee -a $(printf %q "$LOG")"
  "$TMUX_BIN" send-keys -t "$target" Enter
  log "armed steward target=$target session=$sess poll=${poll}s project=$PROJECT"
  echo "armed $target"
}

cmd_disarm() {
  local target sess
  cmd_disarm_state
  target="$(steward_tmux_target 2>/dev/null || echo steward:1.1)"
  sess="$(tmux_session_from_target "$target")"
  if "$TMUX_BIN" has-session -t "$sess" 2>/dev/null; then
    "$TMUX_BIN" send-keys -t "$target" C-c 2>/dev/null || true
  fi
  log "disarmed project=$PROJECT target=$target"
  echo "disarmed"
}

bag_snapshot() {
  if [[ -n "$VIVI_BIN" && -x "$VIVI_BIN" ]]; then
    "$VIVI_BIN" mailspace status --project "$PROJECT" 2>/dev/null | head -40 || true
  else
    echo "(vivi unavailable)"
  fi
}

notify_board() {
  local meta fleet last age grace body subj
  meta="$(py notify_meta)"
  fleet="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("fleet") or d.get("fleet") or "fleet")')"
  last="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["last_successful_cycle_at"])')"
  age="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("age_sec"))')"
  grace="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["grace_sec"])')"
  if ! echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("operator_board") else 1)'; then
    log "skip operator board notify"
    return 0
  fi
  [[ -n "$VIVI_BIN" && -x "$VIVI_BIN" ]] || { log "vivi missing; skip board notify"; return 0; }
  # ensure operator identity
  "$VIVI_BIN" mailspace identity list --project "$PROJECT" 2>/dev/null | grep -q '^operator' \
    || "$VIVI_BIN" mailspace identity add operator --project "$PROJECT" 2>/dev/null || true

  subj="operator: problem — steward trip — ${fleet}"
  body="$(cat <<EOF
## Steward dead-man trip

Mind completed-cycle ticks stopped past grace. Fleet held.

| Field | Value |
| --- | --- |
| project | $PROJECT |
| fleet | $fleet |
| last_successful_cycle_at | $last |
| age_sec | $age |
| grace_sec | $grace |
| action | hold — Hands: finish open bag only if idle; do not invent new map packages |

Reattach Mind: clear with \`steward.sh clear --project $PROJECT\`, fix loop/hooks, rearm.

## Bag snapshot
\`\`\`
$(bag_snapshot)
\`\`\`
EOF
)"
  "$VIVI_BIN" need send --project "$PROJECT" --from mind --to operator \
    --subject "$subj" --body "$body" 2>&1 | tee -a "$LOG" || \
  "$VIVI_BIN" mail send --project "$PROJECT" --from mind --to operator \
    --subject "$subj" --body "$body" 2>&1 | tee -a "$LOG" || \
    log "board notify failed"
}

notify_external() {
  local meta account to_json fleet last age grace subj body draft_out draft_path to_args
  meta="$(py notify_meta)"
  if ! echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; d=json.load(sys.stdin); raise SystemExit(0 if d.get("external_email") and d.get("preauthorized") else 1)'; then
    log "skip external email (disabled or not preauthorized)"
    return 0
  fi
  if echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("skip_external_dedupe") else 1)'; then
    log "skip external email (dedupe window)"
    return 0
  fi
  [[ -n "$VIVI_BIN" && -x "$VIVI_BIN" ]] || { log "vivi missing; skip external"; py mark_external err "vivi missing"; return 0; }

  account="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("account") or "")')"
  fleet="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("fleet") or d.get("fleet") or "fleet")')"
  last="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["last_successful_cycle_at"])')"
  age="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("age_sec"))')"
  grace="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["grace_sec"])')"
  [[ -n "$account" ]] || { log "no notify.account"; py mark_external err "no account"; return 0; }

  to_args=()
  while IFS= read -r addr; do
    [[ -n "$addr" ]] && to_args+=(--to "$addr")
  done < <(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; [print(t) for t in json.load(sys.stdin).get("to") or []]')
  if [[ ${#to_args[@]} -eq 0 ]]; then
    log "no notify.to addresses"
    py mark_external err "no to"
    return 0
  fi

  subj="[fleet steward] ${fleet}: Mind ticks stopped — holding"
  body="$(printf 'Fleet steward trip\n\nFleet: %s\nProject: %s\nLast successful Mind cycle: %s\nAge: %ss (grace %ss)\n\nSteward is holding this fleet (no new map packages). Reattach Mind, run steward.sh clear, fix the Grok loop/hooks, then rearm.\n\n— fleet steward (preauthorized trip page only)\n' \
    "$fleet" "$PROJECT" "$last" "$age" "$grace")"

  draft_out="$(
    "$VIVI_BIN" compose --account "$account" "${to_args[@]}" \
      --subject "$subj" --body "$body" --html-body-auto 2>&1
  )" || { log "compose failed: $draft_out"; py mark_external err "compose failed"; return 0; }
  log "compose: $draft_out"
  draft_path="$(echo "$draft_out" | "$PYTHON_BIN" -c '
import sys,re
t=sys.stdin.read()
# path-like .eml
m=re.search(r"(/[^\s\"]+\.eml)", t)
if m: print(m.group(1)); raise SystemExit
m=re.search(r"([^\s\"]+\.eml)", t)
print(m.group(1) if m else "")
')"
  if [[ -z "$draft_path" || ! -f "$draft_path" ]]; then
    log "could not parse draft path from compose output"
    py mark_external err "no draft path"
    return 0
  fi
  if "$VIVI_BIN" exec send --account "$account" "$draft_path" 2>&1 | tee -a "$LOG"; then
    py mark_external ok
    log "external page sent account=$account"
  else
    py mark_external err "exec send failed"
    log "external page send failed"
  fi
}

soft_hold_hands() {
  local meta mode name target pane sess
  meta="$(py notify_meta)"
  mode="$(echo "$meta" | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("mode","hold"))')"
  [[ "$mode" == "hold" ]] || { log "mode=$mode skip hand pointers"; return 0; }
  # Use fleet.json hand tmux_targets only (this fleet — never other fleets)
  while IFS=$'\t' read -r name target; do
    [[ -n "$target" ]] || continue
    sess="${target%%:*}"
    if ! "$TMUX_BIN" has-session -t "$sess" 2>/dev/null; then
      log "hand $name session $sess missing — skip"
      continue
    fi
    pane="$("$TMUX_BIN" capture-pane -t "$target" -p -S -8 2>/dev/null || true)"
    if echo "$pane" | grep -qE 'Waiting for response|Responding|Working'; then
      log "hand $name ($target) looks running — no pointer"
      continue
    fi
    "$TMUX_BIN" send-keys -t "$target" -l "STEWARD HOLD: Mind ticks stopped. Finish open bag only if mid-unit; then idle. No new map packages. Operator paged."
    "$TMUX_BIN" send-keys -t "$target" Enter
    log "hold pointer sent to $name target=$target"
  done < <(echo "$meta" | "$PYTHON_BIN" -c '
import json, sys
for h in json.load(sys.stdin).get("hand_targets") or []:
    print("%s\t%s" % (h.get("name", ""), h.get("tmux_target", "")))
')
}

do_trip() {
  local reason="${1:-missed_successful_cycle}"
  log "TRIP reason=$reason project=$PROJECT"
  py mark_tripped "$reason"
  notify_board
  notify_external
  soft_hold_hands
  log "trip complete"
}

cmd_check() {
  set +e
  out="$(py should_trip 2>&1)"
  rc=$?
  set -e
  log "check: $out (rc=$rc)"
  if [[ $rc -eq 1 ]]; then
    do_trip "missed_successful_cycle"
    exit 1
  fi
  exit "$rc"
}

cmd_trip() {
  do_trip "${1:-manual_trip}"
  exit 1
}

cmd_loop() {
  local poll
  poll="$(py cfg | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin)["poll_sec"])')"
  log "loop start poll=${poll}s project=$PROJECT"
  while true; do
    set +e
    out="$(py should_trip 2>&1)"
    rc=$?
    set -e
    log "loop tick: $out (rc=$rc)"
    if [[ $rc -eq 1 ]]; then
      do_trip "missed_successful_cycle"
      # after trip, idle until clear/disarm (do not spam)
      while true; do
        sleep "$poll"
        armed="$(py status | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("armed"))')"
        tripped="$(py status | "$PYTHON_BIN" -c 'import json,sys; print(json.load(sys.stdin).get("tripped"))')"
        if [[ "$armed" != "True" && "$armed" != "true" ]]; then
          log "loop exit: disarmed"
          exit 3
        fi
        if [[ "$tripped" != "True" && "$tripped" != "true" ]]; then
          log "loop: trip cleared; resume watch"
          break
        fi
        log "loop: still tripped; waiting"
      done
    elif [[ $rc -eq 3 ]]; then
      log "loop exit: inactive/disarmed"
      exit 3
    elif [[ $rc -eq 2 ]]; then
      log "loop config error: $out"
      sleep "$poll"
    else
      sleep "$poll"
    fi
  done
}

case "${CMD}" in
  arm) cmd_arm ;;
  rearm) cmd_rearm ;;
  disarm) cmd_disarm ;;
  status) cmd_status ;;
  check) cmd_check ;;
  clear) cmd_clear ;;
  trip) cmd_trip "$@" ;;
  loop) cmd_loop ;;
  help|"") usage ;;
  *) echo "unknown command: $CMD" >&2; usage ;;
esac
