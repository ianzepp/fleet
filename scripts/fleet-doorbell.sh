#!/usr/bin/env bash
# Pointer-only Hand/Head wake via fleet.json tmux_target.
#
# Usage:
#   fleet-doorbell.sh --project <root> <hand-name> [--handle HEX] [--note '…'] [--force]
#   fleet-doorbell.sh --project <root> --target mgs:hand-1.1 --message 'HAND WAKE …'
#
# Requires: bash 3.2+ (not sh/zsh-as-script), python3 >= 3.9
# Backing runtime: tmux (default) or vivi-pty for roles with runtime.kind=vivi_pty.
# Portable: macOS + Linux. Override with TMUX_BIN / VIVI_PTY_BIN / PYTHON_BIN /
# FLEET_DOORBELL_SUBMIT_DELAY_SEC.
#
# Rate limit (min_seconds_between_wakes): only if this Hand has prior wake
# count >= 1 in baseline last_hand_wake.by_hand.<name>. First wake never limited.
#
# Exit: 0 sent · 1 refused (running / rate-limit / missing) · 2 usage/config error
set -euo pipefail

_FLEET_SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=lib/env.sh
. "$_FLEET_SCRIPT_DIR/lib/env.sh"
fleet_bootstrap_env

PROJECT=""
NAME=""
HANDLE=""
NOTE=""
FORCE=0
TARGET=""
MESSAGE=""
SUBMIT_DELAY="${FLEET_DOORBELL_SUBMIT_DELAY_SEC:-}"

if ! PYTHON_BIN="$(fleet_find_python3)"; then
  echo "ERROR: python3 >= 3.9 not found (set PYTHON_BIN)" >&2
  exit 2
fi
# tmux is only required for tmux-backed roles; vivi_pty roles use vivi-pty.
TMUX_BIN=""
VIVI_PTY_BIN=""
find_backing_tools() {
  if [[ "$WAKE_MODE" == "vivi_pty" ]]; then
    if ! VIVI_PTY_BIN="$(fleet_find_vivi_pty)"; then
      echo "ERROR: vivi-pty not found (set VIVI_PTY_BIN)" >&2
      exit 2
    fi
  else
    if ! TMUX_BIN="$(fleet_find_tmux)"; then
      echo "ERROR: tmux not found (set TMUX_BIN)" >&2
      exit 2
    fi
  fi
}

usage() {
  fleet_usage_from_header "$0" 2 12
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project|-p)
      fleet_need_optarg "$1" "${2-}" || usage
      PROJECT="$2"
      shift 2
      ;;
    --handle)
      fleet_need_optarg "$1" "${2-}" || usage
      HANDLE="$2"
      shift 2
      ;;
    --note)
      fleet_need_optarg "$1" "${2-}" || usage
      NOTE="$2"
      shift 2
      ;;
    --force) FORCE=1; shift ;;
    --target)
      fleet_need_optarg "$1" "${2-}" || usage
      TARGET="$2"
      shift 2
      ;;
    --message)
      fleet_need_optarg "$1" "${2-}" || usage
      MESSAGE="$2"
      shift 2
      ;;
    -h|--help) usage ;;
    --)
      shift
      break
      ;;
    -*)
      echo "unknown arg: $1" >&2
      usage
      ;;
    *)
      if [[ -z "$NAME" ]]; then
        NAME="$1"
        shift
      else
        echo "unknown arg: $1" >&2
        usage
      fi
      ;;
  esac
done

[[ -n "$PROJECT" ]] || usage
if ! PROJECT="$(fleet_abs_project "$PROJECT")"; then
  echo "ERROR: project is not a directory: $PROJECT" >&2
  exit 2
fi
FLEET="${FLEET:-$PROJECT/.vivi/fleet.json}"
BASELINE="${BASELINE:-$PROJECT/.vivi/mind-baseline.json}"
[[ -f "$FLEET" ]] || { echo "missing fleet.json: $FLEET" >&2; exit 2; }

# Resolve hand slot from fleet.json (embedded python — portable, no zsh).
# Emits a single line of shell-evaluable key=value pairs, one per line, ending with __RESOLVE_END__.
resolve() {
  "$PYTHON_BIN" - "$FLEET" "$BASELINE" "${NAME:-}" "${TARGET:-}" "$PROJECT" <<'PY'
import json, sys
from pathlib import Path

fleet_path, baseline_path, name, target_override, project = sys.argv[1:6]

def load(path):
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

f = load(fleet_path)
b = load(baseline_path)
project = Path(project)

hands = f.get("hands") or f.get("hunters") or {}
slot = None
if name and name in hands:
    slot = hands[name]
elif name:
    candidate = f.get(name)
    if not isinstance(candidate, dict):
        candidate = (f.get("heads") or {}).get(name)
    if isinstance(candidate, dict):
        slot = candidate

runtime = (slot or {}).get("runtime") or {}
runtime_kind = runtime.get("kind") if isinstance(runtime, dict) else None
wake_mode = "vivi_pty" if runtime_kind == "vivi_pty" else ((slot or {}).get("wake_mode") or "tmux_send_keys")

if target_override:
    target = target_override
    session = target.split(":")[0]
    agent = (slot or {}).get("agent") or "unknown"
    min_gap = int((slot or {}).get("min_seconds_between_wakes") or 0)
    mail = (slot or {}).get("mail_identity") or name or "hand"
    socket = ""
elif slot:
    if wake_mode == "vivi_pty":
        session_id = (runtime.get("session_id") if isinstance(runtime, dict) else None) or (slot.get("mail_identity") or name)
        socket = (runtime.get("socket") if isinstance(runtime, dict) else None) or str(project / ".vivi" / "vivi-pty.sock")
        target = session_id
        session = socket
        agent = slot.get("agent") or "unknown"
        min_gap_value = slot.get("min_seconds_between_wakes")
        min_gap = int(180 if min_gap_value is None else min_gap_value)
        mail = slot.get("mail_identity") or name
    else:
        target = slot.get("tmux_target") or ("%s:1.1" % (slot.get("tmux_session") or name))
        session = target.split(":")[0]
        agent = slot.get("agent") or "unknown"
        min_gap_value = slot.get("min_seconds_between_wakes")
        min_gap = int(180 if min_gap_value is None else min_gap_value)
        mail = slot.get("mail_identity") or name
        socket = ""
else:
    sys.stderr.write("error: unknown slot\n")
    sys.exit(2)

# Rate-limit stamps are PER-HAND only (last_hand_wake.by_hand.<name>).
# Never use top-level last_hand_wake_target / last_hand_wake_at alone — gatherer-era
# baselines leave stale last_hand_wake_target=hand-N while last_hand_wake_at is
# another Hand's timestamp, which falsely rate-limits the wrong slot every cycle.
by = ((b.get("last_hand_wake") or {}).get("by_hand") or {})
per = by.get(name) if name else None
if isinstance(per, dict) and per.get("at"):
    last_at = per.get("at") or ""
    wake_count = int(per.get("count") or 0)
else:
    last_at = ""
    wake_count = 0
    # Legacy only: structured last_hand_wake.target must match this hand (not
    # the separate top-level last_hand_wake_target field).
    gl = b.get("last_hand_wake") if isinstance(b.get("last_hand_wake"), dict) else {}
    if gl.get("target") == name and (gl.get("at") or b.get("last_hand_wake_at")):
        last_at = gl.get("at") or b.get("last_hand_wake_at") or ""
        wake_count = 1 if last_at else 0

out = {
    "target": target,
    "session": session,
    "agent": agent,
    "min_gap": min_gap,
    "mail": mail or "",
    "last_at": last_at or "",
    "name": name or "",
    "wake_count": int(wake_count),
    "wake_mode": wake_mode,
    "socket": socket or "",
}
for key in ("target", "session", "agent", "min_gap", "mail", "last_at", "name", "wake_count", "wake_mode", "socket"):
    sys.stdout.buffer.write(str(out[key]).encode("utf-8") + b"\0")
PY
}

# Classify pane quickly (subset of fleet-sensors heuristics; BSD+GNU grep -Eiq).
classify() {
  local target=$1
  local session=${target%%:*}
  local t class
  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    echo stopped
    return 0
  fi
  t="$("$TMUX_BIN" capture-pane -t "$target" -p -S -20 2>/dev/null || true)"
  # Order matters: first match wins.
  for class in \
    'running|Working \(|esc to interrupt|Waiting for response|Responding' \
    'approval_required|Yes, continue|Do you trust|trust this workspace|Always allow|Allow always|Allow once|until OpenCode is restarted' \
    'failed|over capacity|rate limit|usage limit'
  do
    if printf '%s\n' "$t" | grep -Eiq "${class#*|}"; then
      echo "${class%%|*}"
      return 0
    fi
  done
  echo waiting_for_input
  return 0
}

# Read vivi-pty's canonical harness state; the driver owns PTY classification.
classify_vivi_pty() {
  local session_id=$1
  local socket=$2
  local diag
  if ! diag=$("$VIVI_PTY_BIN" session diagnostic "$session_id" --socket "$socket" 2>/dev/null); then
    echo stopped
    return 0
  fi
  printf '%s\n' "$diag" | "$PYTHON_BIN" -c '
import json, sys
try:
    data = json.load(sys.stdin)
    process = data.get("process_state") or data.get("session", {}).get("state")
    print("stopped" if process in ("exited", "stopped") else data.get("harness_state", "unknown"))
except Exception:
    print("unknown")
'
}

RESOLVED_TARGET=""
SESSION=""
AGENT="unknown"
MIN_GAP=0
MAIL=""
LAST_AT=""
LAST_TARGET=""

if [[ -n "$MESSAGE" && -n "$TARGET" ]]; then
  RESOLVED_TARGET="$TARGET"
  WAKE_MODE="tmux_send_keys"
  AGENT="unknown"
  MAIL="${NAME:-}"
  MIN_GAP=0
  LAST_AT=""
  WAKE_COUNT=0
  SOCKET=""
  SESSION="${TARGET%%:*}"
elif [[ -n "$NAME" ]]; then
  # Read fixed-order NUL-delimited values; never eval editable fleet JSON.
  _resolve_values=()
  while IFS= read -r -d '' _resolve_value; do
    _resolve_values+=("$_resolve_value")
  done < <(resolve)
  [[ ${#_resolve_values[@]} -eq 10 ]] || { echo "ERROR: failed to resolve runtime binding" >&2; exit 2; }
  RESOLVED_TARGET="${_resolve_values[0]}"
  SESSION="${_resolve_values[1]}"
  AGENT="${_resolve_values[2]}"
  MIN_GAP="${_resolve_values[3]}"
  MAIL="${_resolve_values[4]}"
  LAST_AT="${_resolve_values[5]}"
  LAST_TARGET="${_resolve_values[6]}"
  WAKE_COUNT="${_resolve_values[7]}"
  WAKE_MODE="${_resolve_values[8]}"
  SOCKET="${_resolve_values[9]}"
else
  usage
fi

WAKE_MODE="${WAKE_MODE:-tmux_send_keys}"
find_backing_tools

# Classify pane/session quickly before sending.
if [[ "$WAKE_MODE" == "vivi_pty" ]]; then
  CLASS="$(classify_vivi_pty "$RESOLVED_TARGET" "$SOCKET")"
else
  CLASS="$(classify "$RESOLVED_TARGET")"
fi
if [[ "$FORCE" -ne 1 && "$CLASS" =~ ^(starting|submitting|running|approval_required|failed)$ ]]; then
  echo "refused: runtime $RESOLVED_TARGET state=$CLASS" >&2
  exit 1
fi
if [[ "$CLASS" == "stopped" ]]; then
  echo "refused: no runtime session for $RESOLVED_TARGET" >&2
  exit 1
fi

# Rate limit only when this Hand has a prior successful doorbell (count>=1 + last_at).
# No last wake / count 0 → never refuse (cold attach, first wake after recreate).
if [[ "$FORCE" -ne 1 && "${WAKE_COUNT:-0}" -ge 1 && -n "${LAST_AT:-}" && "${MIN_GAP:-0}" -gt 0 ]]; then
  NOW_EPOCH="$(fleet_date_epoch)"
  LAST_EPOCH="$("$PYTHON_BIN" -c '
import sys
from datetime import datetime, timezone
s = sys.argv[1].strip()
if not s:
    print(0); raise SystemExit
if s.endswith("Z") or s.endswith("z"):
    s = s[:-1] + "+00:00"
try:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    print(int(dt.timestamp()))
except Exception:
    print(0)
' "${LAST_AT}")"
  if [[ "$LAST_EPOCH" -gt 0 ]]; then
    DELTA=$((NOW_EPOCH - LAST_EPOCH))
    if [[ "$DELTA" -lt "$MIN_GAP" ]]; then
      echo "refused: rate limit ${DELTA}s < ${MIN_GAP}s since last wake of $NAME (count=${WAKE_COUNT})" >&2
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

# strip newlines / CRs from pointer (portable tr)
MESSAGE="$(printf '%s' "$MESSAGE" | tr '\n\r' '  ')"

if [[ "$WAKE_MODE" == "vivi_pty" ]]; then
  if [[ -z "$SUBMIT_DELAY" ]]; then
    SUBMIT_DELAY="0.05"
  fi
  "$VIVI_PTY_BIN" terminal write "$RESOLVED_TARGET" "$MESSAGE" --enter --socket "$SOCKET"
  sleep "$SUBMIT_DELAY"
else
  "$TMUX_BIN" send-keys -t "$RESOLVED_TARGET" -l -- "$MESSAGE"
  if [[ -z "$SUBMIT_DELAY" ]]; then
    case "$AGENT" in
      codex) SUBMIT_DELAY="0.8" ;;
      grok|pi|opencode) SUBMIT_DELAY="0.05" ;;
      *) SUBMIT_DELAY="0.05" ;;
    esac
  fi
  sleep "$SUBMIT_DELAY"
  "$TMUX_BIN" send-keys -t "$RESOLVED_TARGET" Enter
fi

# record last wake in baseline (atomic write)
"$PYTHON_BIN" - "$BASELINE" "$PROJECT" "$NAME" "$HANDLE" "$RESOLVED_TARGET" "$WAKE_MODE" "$SOCKET" <<'PY'
import json, os, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone

path, project, name, handle, target, wake_mode, socket = sys.argv[1:8]
p = Path(path)
b = {}
if p.is_file():
    try:
        b = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        b = {}
now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
b["project"] = b.get("project") or project
b["last_hand_wake_at"] = now
prev = b.get("last_hand_wake") if isinstance(b.get("last_hand_wake"), dict) else {}
by = prev.get("by_hand") if isinstance(prev.get("by_hand"), dict) else {}
key = name or target
old = by.get(key) if isinstance(by.get(key), dict) else {}
count = int(old.get("count") or 0) + 1
runtime = {"kind": "vivi_pty" if wake_mode == "vivi_pty" else "tmux", "target": target}
if socket:
    runtime["socket"] = socket
entry = {"at": now, "count": count, "handle": handle or None, "runtime": runtime}
for prior in by.values():
    if not isinstance(prior, dict):
        continue
    if not isinstance(prior.get("runtime"), dict):
        kind = prior.get("runtime_kind") or ("tmux" if prior.get("tmux_target") else None)
        target_value = prior.get("runtime_target") or prior.get("tmux_target")
        if kind and target_value:
            prior["runtime"] = {"kind": kind, "target": target_value}
            if prior.get("runtime_socket"):
                prior["runtime"]["socket"] = prior["runtime_socket"]
    for stale in ("runtime_kind", "runtime_target", "runtime_socket", "tmux_target"):
        prior.pop(stale, None)
by[key] = entry
b["last_hand_wake"] = {
    "target": key,
    "handle": handle or None,
    "runtime": runtime,
    "at": now,
    "reason": "doorbell",
    "by_hand": by,
}
b["last_hand_wake_at"] = now
b.pop("last_hand_wake_target", None)
p.parent.mkdir(parents=True, exist_ok=True)
text = json.dumps(b, indent=2, ensure_ascii=False) + "\n"
fd, tmp = tempfile.mkstemp(prefix=".%s." % p.name, suffix=".tmp", dir=str(p.parent))
try:
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, p)
except Exception:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise
sys.stdout.write("sent\t%s\t%s\t%s\t%s\n" % (target, name or "", handle or "", now))
PY

exit 0
