#!/bin/bash
# Pointer-only Hand/Head wake via fleet.json tmux_target.
#
# Usage:
#   fleet-doorbell.sh --project <root> <hand-name> [--handle HEX] [--note '…'] [--force]
#   fleet-doorbell.sh --project <root> --target mgs:hand-1.1 --message 'HAND WAKE …'
#
# Exit: 0 sent · 1 refused (running / rate-limit / missing) · 2 usage/config error
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${HOME}/.cargo/bin:${HOME}/.local/bin:${PATH:-}"

PROJECT=""
NAME=""
HANDLE=""
NOTE=""
FORCE=0
TARGET=""
MESSAGE=""
TMUX_BIN="${TMUX_BIN:-$(command -v tmux 2>/dev/null || echo /opt/homebrew/bin/tmux)}"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 2>/dev/null || echo /usr/bin/python3)}"
SELF_DIR="$(cd "$(dirname "$0")" && pwd)"

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project|-p) PROJECT="$2"; shift 2 ;;
    --handle) HANDLE="$2"; shift 2 ;;
    --note) NOTE="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --target) TARGET="$2"; shift 2 ;;
    --message) MESSAGE="$2"; shift 2 ;;
    -h|--help) usage ;;
    *)
      if [[ -z "$NAME" && "$1" != --* ]]; then
        NAME="$1"; shift
      else
        echo "unknown arg: $1" >&2
        usage
      fi
      ;;
  esac
done

[[ -n "$PROJECT" ]] || usage
PROJECT="$(cd "$PROJECT" && pwd)"
FLEET="${FLEET:-$PROJECT/.vivi/fleet.json}"
BASELINE="${BASELINE:-$PROJECT/.vivi/mind-baseline.json}"
[[ -f "$FLEET" ]] || { echo "missing fleet.json: $FLEET" >&2; exit 2; }

# Resolve hand slot from fleet.json
resolve() {
  "$PYTHON_BIN" - "$FLEET" "$BASELINE" "${NAME:-}" "${TARGET:-}" <<'PY'
import json, sys, time
from pathlib import Path
from datetime import datetime, timezone

fleet_path, baseline_path, name, target_override = sys.argv[1:5]
f = json.loads(Path(fleet_path).read_text())
b = {}
if Path(baseline_path).is_file():
    try:
        b = json.loads(Path(baseline_path).read_text())
    except Exception:
        b = {}

hands = f.get("hands") or f.get("hunters") or {}
slot = None
if name and name in hands:
    slot = hands[name]
elif name:
    for key in ("head-ceo", "head-cto", "head-cxo", "steward"):
        if name == key and isinstance(f.get(key), dict):
            slot = f[key]
            break

if target_override:
    target = target_override
    session = target.split(":")[0]
    agent = (slot or {}).get("agent") or "unknown"
    min_gap = int((slot or {}).get("min_seconds_between_wakes") or 0)
    wake_enabled = True if not slot else bool(slot.get("wake_enabled", True))
    mail = (slot or {}).get("mail_identity") or name or "hand"
elif slot:
    target = slot.get("tmux_target") or f"{slot.get('tmux_session') or name}:1.1"
    session = target.split(":")[0]
    agent = slot.get("agent") or "unknown"
    min_gap = int(slot.get("min_seconds_between_wakes") or 180)
    wake_enabled = bool(slot.get("wake_enabled", True))
    mail = slot.get("mail_identity") or name
else:
    print("error\tunknown slot", file=sys.stderr)
    sys.exit(2)

# last wake for rate limit
last_at = b.get("last_hand_wake_at") or b.get("last_hunter_wake_at")
last_wake = b.get("last_hand_wake") or {}
print(f"{target}\t{session}\t{agent}\t{min_gap}\t{int(wake_enabled)}\t{mail}\t{last_at or ''}\t{last_wake.get('target') or ''}")
PY
}

# Classify pane quickly (same heuristics as sensors subset)
classify() {
  local target=$1
  local session=${target%%:*}
  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    echo down
    return
  fi
  local t
  t="$("$TMUX_BIN" capture-pane -t "$target" -p -S -20 2>/dev/null || true)"
  if echo "$t" | grep -Eiq 'Working \(|esc to interrupt|Waiting for response|Responding'; then
    echo running
    return
  fi
  if echo "$t" | grep -Eiq 'Yes, continue|Do you trust|trust this workspace'; then
    echo trust_prompt
    return
  fi
  if echo "$t" | grep -Eiq 'over capacity|rate limit|usage limit'; then
    echo error_capacity
    return
  fi
  echo idle
}

if [[ -n "$MESSAGE" && -n "$TARGET" ]]; then
  RESOLVED_TARGET="$TARGET"
  AGENT="unknown"
  MIN_GAP=0
  WAKE_EN=1
  MAIL=""
elif [[ -n "$NAME" ]]; then
  IFS=$'\t' read -r RESOLVED_TARGET SESSION AGENT MIN_GAP WAKE_EN MAIL LAST_AT LAST_TARGET < <(resolve)
else
  usage
fi

if [[ "${WAKE_EN:-1}" -eq 0 && "$FORCE" -ne 1 ]]; then
  echo "refused: wake_enabled=false for $NAME" >&2
  exit 1
fi

CLASS="$(classify "$RESOLVED_TARGET")"
if [[ "$CLASS" == "running" && "$FORCE" -ne 1 ]]; then
  echo "refused: pane $RESOLVED_TARGET is running" >&2
  exit 1
fi
if [[ "$CLASS" == "down" ]]; then
  echo "refused: no session for $RESOLVED_TARGET" >&2
  exit 1
fi

# rate limit
if [[ "$FORCE" -ne 1 && -n "${LAST_AT:-}" && "${MIN_GAP:-0}" -gt 0 ]]; then
  NOW_EPOCH=$(date -u +%s)
  LAST_EPOCH=$("$PYTHON_BIN" -c "
from datetime import datetime, timezone
import sys
s=sys.argv[1].replace('Z','+00:00')
try:
  dt=datetime.fromisoformat(s)
  if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
  print(int(dt.timestamp()))
except Exception:
  print(0)
" "${LAST_AT}")
  if [[ "$LAST_EPOCH" -gt 0 ]]; then
    DELTA=$((NOW_EPOCH - LAST_EPOCH))
    if [[ "$DELTA" -lt "$MIN_GAP" && "${LAST_TARGET:-}" == "$NAME" ]]; then
      echo "refused: rate limit ${DELTA}s < ${MIN_GAP}s since last wake of $NAME" >&2
      exit 1
    fi
  fi
fi

# Build pointer message
if [[ -z "$MESSAGE" ]]; then
  PROJECT_Q="$PROJECT"
  MAIL_Q="${MAIL:-$NAME}"
  if [[ -n "$HANDLE" ]]; then
    MESSAGE="HAND WAKE ${NAME}. Bag: show ${HANDLE}. vivi --project ${PROJECT_Q} --for ${MAIL_Q}. ${NOTE} Continue."
  else
    MESSAGE="HAND WAKE ${NAME}. Bag: show next open. vivi --project ${PROJECT_Q} --for ${MAIL_Q}. ${NOTE} Continue."
  fi
fi

# strip newlines from pointer
MESSAGE="$(printf '%s' "$MESSAGE" | tr '\n' ' ')"

"$TMUX_BIN" send-keys -t "$RESOLVED_TARGET" -l -- "$MESSAGE"
"$TMUX_BIN" send-keys -t "$RESOLVED_TARGET" Enter

# record last wake in baseline
"$PYTHON_BIN" - "$BASELINE" "$PROJECT" "$NAME" "$HANDLE" "$RESOLVED_TARGET" <<'PY'
import json, sys
from pathlib import Path
from datetime import datetime, timezone
path, project, name, handle, target = sys.argv[1:6]
p = Path(path)
b = {}
if p.is_file():
    try:
        b = json.loads(p.read_text())
    except Exception:
        b = {}
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
b["project"] = b.get("project") or project
b["last_hand_wake_at"] = now
b["last_hand_wake"] = {
    "target": name or target,
    "handle": handle or None,
    "tmux_target": target,
    "at": now,
    "reason": "doorbell",
}
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(b, indent=2) + "\n")
print(f"sent\t{target}\t{name or ''}\t{handle or ''}\t{now}")
PY

exit 0
