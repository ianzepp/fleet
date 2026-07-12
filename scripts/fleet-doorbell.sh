#!/usr/bin/env bash
# Pointer-only Hand/Head wake via fleet.json tmux_target.
#
# Usage:
#   fleet-doorbell.sh --project <root> <hand-name> [--handle HEX] [--note '…'] [--force]
#   fleet-doorbell.sh --project <root> --target mgs:hand-1.1 --message 'HAND WAKE …'
#
# Requires: bash 3.2+ (not sh/zsh-as-script), python3 >= 3.9, tmux
# Portable: macOS + Linux. Override with TMUX_BIN / PYTHON_BIN /
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

if ! TMUX_BIN="$(fleet_find_tmux)"; then
  echo "ERROR: tmux not found (set TMUX_BIN)" >&2
  exit 2
fi
if ! PYTHON_BIN="$(fleet_find_python3)"; then
  echo "ERROR: python3 >= 3.9 not found (set PYTHON_BIN)" >&2
  exit 2
fi

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

# Resolve hand slot from fleet.json (embedded python — portable, no zsh)
resolve() {
  "$PYTHON_BIN" - "$FLEET" "$BASELINE" "${NAME:-}" "${TARGET:-}" <<'PY'
import json, sys
from pathlib import Path

fleet_path, baseline_path, name, target_override = sys.argv[1:5]

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

if target_override:
    target = target_override
    session = target.split(":")[0]
    agent = (slot or {}).get("agent") or "unknown"
    min_gap = int((slot or {}).get("min_seconds_between_wakes") or 0)
    wake_enabled = True if not slot else bool(slot.get("wake_enabled", True))
    mail = (slot or {}).get("mail_identity") or name or "hand"
elif slot:
    target = slot.get("tmux_target") or ("%s:1.1" % (slot.get("tmux_session") or name))
    session = target.split(":")[0]
    agent = slot.get("agent") or "unknown"
    min_gap = int(slot.get("min_seconds_between_wakes") or 180)
    wake_enabled = bool(slot.get("wake_enabled", True))
    mail = slot.get("mail_identity") or name
else:
    sys.stderr.write("error\tunknown slot\n")
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
# TSV — tabs only; values must not contain tabs
# last field: per-hand wake count (0 = never woken this tracking era → no rate limit)
fields = [
    target,
    session,
    agent,
    str(min_gap),
    str(int(wake_enabled)),
    mail or "",
    last_at or "",
    name or "",
    str(int(wake_count)),
]
sys.stdout.write("\t".join(fields) + "\n")
PY
}

# Classify pane quickly (subset of fleet-sensors heuristics; BSD+GNU grep -Eiq).
classify() {
  local target=$1
  local session=${target%%:*}
  local t class
  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    echo down
    return 0
  fi
  t="$("$TMUX_BIN" capture-pane -t "$target" -p -S -20 2>/dev/null || true)"
  # Order matters: first match wins.
  for class in \
    'running|Working \(|esc to interrupt|Waiting for response|Responding' \
    'trust_prompt|Yes, continue|Do you trust|trust this workspace' \
    'error_capacity|over capacity|rate limit|usage limit'
  do
    if printf '%s\n' "$t" | grep -Eiq "${class#*|}"; then
      echo "${class%%|*}"
      return 0
    fi
  done
  echo idle
  return 0
}

RESOLVED_TARGET=""
SESSION=""
AGENT="unknown"
MIN_GAP=0
WAKE_EN=1
MAIL=""
LAST_AT=""
LAST_TARGET=""

if [[ -n "$MESSAGE" && -n "$TARGET" ]]; then
  RESOLVED_TARGET="$TARGET"
elif [[ -n "$NAME" ]]; then
  # Process substitution is bash-only (required). Bash 3.2+ OK.
  # Avoid pipeline so resolve failures trip set -e.
  _resolve_out="$(resolve)" || exit $?
  # shellcheck disable=SC2034
  IFS="$(printf '\t')" read -r RESOLVED_TARGET SESSION AGENT MIN_GAP WAKE_EN MAIL LAST_AT LAST_TARGET WAKE_COUNT <<EOF
$_resolve_out
EOF
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

# record last wake in baseline (atomic write)
"$PYTHON_BIN" - "$BASELINE" "$PROJECT" "$NAME" "$HANDLE" "$RESOLVED_TARGET" <<'PY'
import json, os, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone

path, project, name, handle, target = sys.argv[1:6]
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
by[key] = {"at": now, "count": count, "handle": handle or None, "tmux_target": target}
b["last_hand_wake"] = {
    "target": key,
    "handle": handle or None,
    "tmux_target": target,
    "at": now,
    "reason": "doorbell",
    "by_hand": by,
}
# Keep legacy fields consistent (prevent stale last_hand_wake_target pinning)
b["last_hand_wake_target"] = key
b["last_hand_wake_at"] = now
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
