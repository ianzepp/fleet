#!/usr/bin/env bash
# Reinit helper for Fleet roles bound to the vivi-pty runtime.
#
# Usage:
#   vivi-pty-reinit.sh --project <root> status hand-2
#   vivi-pty-reinit.sh --project <root> doctor [hand-2]
#   vivi-pty-reinit.sh --project <root> heal   [hand-2]
#   vivi-pty-reinit.sh --project <root> reinit hand-2 [--boot 'pointer text']
#
# Exit: 0 ok · 1 hard fail · 2 session exists but harness is stuck/idle
set -euo pipefail

_FLEET_SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=lib/env.sh
. "$_FLEET_SCRIPT_DIR/lib/env.sh"
fleet_bootstrap_env

PROJECT=""
COMMAND=""
NAME=""
BOOT=""
BOOT_FILE=""
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project|-p)
      fleet_need_optarg "$1" "${2-}" || usage
      PROJECT="$2"
      shift 2
      ;;
    --force) FORCE=1; shift ;;
    --boot)
      fleet_need_optarg "$1" "${2-}" || usage
      BOOT="$2"
      shift 2
      ;;
    --boot-file)
      fleet_need_optarg "$1" "${2-}" || usage
      BOOT_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    -*)
      echo "unknown arg: $1" >&2
      usage
      ;;
    *)
      if [[ -z "$COMMAND" ]]; then
        COMMAND="$1"
        shift
      elif [[ -z "$NAME" ]]; then
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
PROJECT="$(fleet_abs_project "$PROJECT")" || { echo "bad project: $PROJECT" >&2; exit 1; }
FLEET="${FLEET:-$PROJECT/.vivi/fleet.json}"
[[ -f "$FLEET" ]] || { echo "missing fleet.json: $FLEET" >&2; exit 1; }

if ! PYTHON_BIN="$(fleet_find_python3)"; then
  echo "ERROR: python3 >= 3.9 not found" >&2
  exit 1
fi
VIVI_PTY_BIN="$(fleet_find_vivi_pty)" || { echo "vivi-pty not found" >&2; exit 1; }
VIVI_BIN="$(fleet_find_vivi 2>/dev/null || true)"

usage() {
  fleet_usage_from_header "$0" 2 20
  exit 2
}

# Resolve a role from fleet.json. Emits key=value lines for eval.
resolve_role() {
  local name=$1
  "$PYTHON_BIN" - "$FLEET" "$PROJECT" "$name" <<'PY'
import json, sys
from pathlib import Path

fleet_path, project, name = sys.argv[1:4]
project = Path(project)
with open(fleet_path, encoding="utf-8") as fh:
    f = json.load(fh)

hands = f.get("hands") or f.get("hunters") or {}
slot = hands.get(name)
if not isinstance(slot, dict):
    slot = f.get(name)
if not isinstance(slot, dict):
    slot = (f.get("heads") or {}).get(name)
if not isinstance(slot, dict):
    sys.stderr.write("unknown role: %s\n" % name)
    sys.exit(1)

runtime = slot.get("runtime") or {}
if not (isinstance(runtime, dict) and runtime.get("kind") == "vivi_pty") and slot.get("wake_mode") != "vivi_pty":
    sys.stderr.write("role %s is not vivi_pty\n" % name)
    sys.exit(1)

session_id = (runtime.get("session_id") if isinstance(runtime, dict) else None) or slot.get("mail_identity") or name
command = runtime.get("command") if isinstance(runtime, dict) else None
if not isinstance(command, list) or not command:
    sys.stderr.write("role %s missing runtime.command\n" % name)
    sys.exit(1)

out = {
    "session_id": session_id,
    "socket": (runtime.get("socket") if isinstance(runtime, dict) else None) or str(project / ".vivi" / "vivi-pty.sock"),
    "cwd": slot.get("cwd") or str(project),
    "driver": (runtime.get("driver") if isinstance(runtime, dict) else None) or slot.get("agent") or "generic",
    "mail_identity": slot.get("mail_identity") or name,
}
for k, v in out.items():
    sys.stdout.write("ROLE_%s=%s\n" % (k, json.dumps(v, ensure_ascii=False)))
# Bash array for the command so it can be passed as separate arguments.
sys.stdout.write("ROLE_command_args=(%s)\n" % " ".join(json.dumps(c, ensure_ascii=False) for c in command))
PY
}

daemon_running() {
  local socket=$1
  [[ -S "$socket" ]] && "$VIVI_PTY_BIN" info --socket "$socket" >/dev/null 2>&1
}

start_daemon() {
  local socket=$1
  local socket_dir
  socket_dir="$(dirname "$socket")"
  [[ -d "$socket_dir" ]] || mkdir -p "$socket_dir"
  nohup "$VIVI_PTY_BIN" daemon --project "$PROJECT" --socket "$socket" >/dev/null 2>&1 &
  local i=0
  while [[ $i -lt 30 ]]; do
    sleep 0.2
    if daemon_running "$socket"; then
      return 0
    fi
    i=$((i + 1))
  done
  echo "daemon failed to start" >&2
  return 1
}

session_exists() {
  local session_id=$1
  local socket=$2
  "$VIVI_PTY_BIN" session inspect "$session_id" --socket "$socket" >/dev/null 2>&1
}

session_state() {
  local session_id=$1
  local socket=$2
  "$VIVI_PTY_BIN" session inspect "$session_id" --socket "$socket" 2>/dev/null | "$PYTHON_BIN" -c '
import json, sys
try:
    print(json.load(sys.stdin).get("state", "unknown"))
except Exception:
    print("unknown")
' 2>/dev/null || echo "unknown"
}

start_session() {
  local session_id=$1
  local socket=$2
  local cwd=$3
  local driver=$4
  shift 4
  "$VIVI_PTY_BIN" session start "$session_id" --driver "$driver" --cwd "$cwd" --socket "$socket" -- "$@" >/dev/null 2>&1 || true
}

stop_session() {
  local session_id=$1
  local socket=$2
  "$VIVI_PTY_BIN" session stop "$session_id" --socket "$socket" >/dev/null 2>&1 || true
}

restart_session() {
  local session_id=$1
  local socket=$2
  "$VIVI_PTY_BIN" session restart "$session_id" --socket "$socket" >/dev/null 2>&1
}

# Boot a newly-created session with a pointer if provided.
 maybe_boot() {
  local session_id=$1
  local socket=$2
  local boot=$3
  if [[ -n "$boot" ]]; then
    boot="${boot//[$'\n\r']/ }"
    "$VIVI_PTY_BIN" terminal write "$session_id" "$boot" --enter --socket "$socket" >/dev/null 2>&1
  fi
}

ensure_role() {
  local name=$1
  eval "$(resolve_role "$name")"
  [[ -n "${ROLE_session_id:-}" ]] || { echo "failed to resolve role" >&2; exit 1; }
  if ! daemon_running "$ROLE_socket"; then
    start_daemon "$ROLE_socket"
  fi
  if ! session_exists "$ROLE_session_id" "$ROLE_socket"; then
    start_session "$ROLE_session_id" "$ROLE_socket" "$ROLE_cwd" "$ROLE_driver" "${ROLE_command_args[@]}"
  fi
}

cmd_status() {
  local name=${1:-}
  if [[ -z "$name" ]]; then
    echo "usage: status <role>" >&2
    exit 1
  fi
  eval "$(resolve_role "$name")"
  printf 'role: %s\nsession_id: %s\nsocket: %s\ndaemon: %s\nsession: %s\n' \
    "$name" "$ROLE_session_id" "$ROLE_socket" \
    "$(daemon_running "$ROLE_socket" && echo up || echo down)" \
    "$(session_exists "$ROLE_session_id" "$ROLE_socket" && echo present || echo absent)"
}

cmd_doctor() {
  local name=${1:-}
  local healthy=0
  if [[ -n "$name" ]]; then
    cmd_status "$name"
    eval "$(resolve_role "$name")"
    if ! daemon_running "$ROLE_socket"; then
      healthy=1
    elif ! session_exists "$ROLE_session_id" "$ROLE_socket"; then
      healthy=1
    else
      local state
      state=$(session_state "$ROLE_session_id" "$ROLE_socket")
      if [[ "$state" == "exited" || "$state" == "stopped" ]]; then
        healthy=1
      fi
    fi
  else
    for r in $("$PYTHON_BIN" - "$FLEET" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    f = json.load(fh)
hands = f.get("hands") or f.get("hunters") or {}
for name, h in hands.items():
    if not isinstance(h, dict):
        continue
    runtime = h.get("runtime") or {}
    if (isinstance(runtime, dict) and runtime.get("kind") == "vivi_pty") or h.get("wake_mode") == "vivi_pty":
        print(name)
PY
); do
      if ! cmd_doctor "$r"; then
        healthy=1
      fi
    done
  fi
  return "$healthy"
}

cmd_heal() {
  local name=${1:-}
  local fail=0
  if [[ -n "$name" ]]; then
    ensure_role "$name"
    maybe_boot "$ROLE_session_id" "$ROLE_socket" "${BOOT:-}"
  else
    for r in $("$PYTHON_BIN" - "$FLEET" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as fh:
    f = json.load(fh)
hands = f.get("hands") or f.get("hunters") or {}
for name, h in hands.items():
    if not isinstance(h, dict):
        continue
    runtime = h.get("runtime") or {}
    if (isinstance(runtime, dict) and runtime.get("kind") == "vivi_pty") or h.get("wake_mode") == "vivi_pty":
        print(name)
PY
); do
      if ! cmd_heal "$r"; then
        fail=1
      fi
    done
  fi
  return "$fail"
}

cmd_reinit() {
  local name=$1
  [[ -n "$name" ]] || { echo "usage: reinit <role>" >&2; exit 1; }
  eval "$(resolve_role "$name")"
  if ! daemon_running "$ROLE_socket"; then
    start_daemon "$ROLE_socket"
  fi
  if session_exists "$ROLE_session_id" "$ROLE_socket"; then
    restart_session "$ROLE_session_id" "$ROLE_socket"
  else
    start_session "$ROLE_session_id" "$ROLE_socket" "$ROLE_cwd" "$ROLE_driver" "${ROLE_command_args[@]}"
  fi
  if [[ -n "${BOOT_FILE:-}" && -f "$BOOT_FILE" ]]; then
    BOOT="$(cat "$BOOT_FILE")"
  fi
  maybe_boot "$ROLE_session_id" "$ROLE_socket" "${BOOT:-}"
}

# Load boot file if provided before dispatch.
if [[ -n "$BOOT_FILE" && -f "$BOOT_FILE" ]]; then
  BOOT="$(cat "$BOOT_FILE")"
fi

case "$COMMAND" in
  status) cmd_status "$NAME" ;;
  doctor) cmd_doctor "$NAME" ;;
  heal) cmd_heal "$NAME" ;;
  reinit) cmd_reinit "$NAME" ;;
  "") usage ;;
  *) echo "unknown command: $COMMAND" >&2; usage ;;
esac
