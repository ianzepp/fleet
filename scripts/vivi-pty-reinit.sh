#!/usr/bin/env bash
# Reinit helper for Fleet roles bound to the vivi-pty runtime.
#
# Usage:
#   vivi-pty-reinit.sh --project <root> status --role hand-2
#   vivi-pty-reinit.sh --project <root> doctor [--role hand-2]
#   vivi-pty-reinit.sh --project <root> heal   [--role hand-2]
#   vivi-pty-reinit.sh --project <root> reinit --role hand-2 [--boot 'pointer text']
#
# Exit: 0 ok · 1 hard fail · 2 session exists but harness is stuck/idle
set -euo pipefail

_FLEET_SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=lib/env.sh
. "$_FLEET_SCRIPT_DIR/lib/env.sh"
fleet_bootstrap_env

PROJECT=""
COMMAND=""
ROLE=""
FLEET_ID=""
FLEET_FILE=""
RUNTIME_TARGET=""
BOOT=""
BOOT_FILE=""
FORCE=0

usage() {
  fleet_usage_from_header "$0" 2 20
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project|-p)
      fleet_need_optarg "$1" "${2-}" || usage
      PROJECT="$2"
      shift 2
      ;;
    --fleet|-f)
      fleet_need_optarg "$1" "${2-}" || usage
      FLEET_ID="$2"
      shift 2
      ;;
    --fleet-file)
      fleet_need_optarg "$1" "${2-}" || usage
      FLEET_FILE="$2"
      shift 2
      ;;
    --runtime-target)
      fleet_need_optarg "$1" "${2-}" || usage
      RUNTIME_TARGET="$2"
      shift 2
      ;;
    --role)
      fleet_need_optarg "$1" "${2-}" || usage
      ROLE="$2"
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
      else
        echo "unexpected positional argument: $1 (use --role)" >&2
        usage
      fi
      ;;
  esac
done

[[ -n "$PROJECT" ]] || usage
PROJECT="$(fleet_abs_project "$PROJECT")" || { echo "bad project: $PROJECT" >&2; exit 1; }
FLEET_FILE="${FLEET_FILE:-$PROJECT/.vivi/fleet.json}"
[[ -f "$FLEET_FILE" ]] || { echo "missing fleet.json: $FLEET_FILE" >&2; exit 1; }

if ! PYTHON_BIN="$(fleet_find_python3)"; then
  echo "ERROR: python3 >= 3.9 not found" >&2
  exit 1
fi
VIVI_PTY_BIN="$(fleet_find_vivi_pty)" || { echo "vivi-pty not found" >&2; exit 1; }
VIVI_BIN="$(fleet_find_vivi 2>/dev/null || true)"

# Resolve a role from fleet.json. Emits key=value lines for eval.
resolve_role() {
  local name=$1
  local resolver=("$PYTHON_BIN" "$_FLEET_SCRIPT_DIR/fleet-resolve.py"
    --project "$PROJECT" --fleet-file "$FLEET_FILE" --role "$name" --shell)
  [[ -n "$FLEET_ID" ]] && resolver+=(--fleet "$FLEET_ID")
  [[ -n "$RUNTIME_TARGET" ]] && resolver+=(--runtime-target "$RUNTIME_TARGET")
  eval "$("${resolver[@]}")"
  [[ "$RESOLVED_KIND" == "vivi_pty" ]] || { echo "role $name is not vivi_pty" >&2; return 1; }
  [[ ${#RESOLVED_RUNTIME_COMMAND[@]} -gt 0 ]] || { echo "role $name missing runtime.command" >&2; return 1; }
  printf 'ROLE_session_id=%q\n' "$RESOLVED_SESSION"
  printf 'ROLE_socket=%q\n' "$RESOLVED_SOCKET"
  printf 'ROLE_cwd=%q\n' "$RESOLVED_CWD"
  printf 'ROLE_driver=%q\n' "$RESOLVED_DRIVER"
  printf 'ROLE_mail_identity=%q\n' "$RESOLVED_MAIL_IDENTITY"
  printf 'ROLE_command_args=(%s)\n' "$(printf '%q ' "${RESOLVED_RUNTIME_COMMAND[@]}")"
}

fleet_roles() {
  local resolver=("$PYTHON_BIN" "$_FLEET_SCRIPT_DIR/fleet-resolve.py"
    --project "$PROJECT" --fleet-file "$FLEET_FILE" --list --kind vivi_pty --group hand)
  [[ -n "$FLEET_ID" ]] && resolver+=(--fleet "$FLEET_ID")
  "${resolver[@]}"
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
    for r in $(fleet_roles); do
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
    for r in $(fleet_roles); do
      if ! cmd_heal "$r"; then
        fail=1
      fi
    done
  fi
  return "$fail"
}

remove_session() {
  local session_id=$1
  local socket=$2
  # Prefer session.remove (no tombstone) so reinit can rebind agent_launch.
  if "$VIVI_PTY_BIN" session remove "$session_id" --socket "$socket" >/dev/null 2>&1; then
    return 0
  fi
  # Older vivi-pty: stop only leaves a tombstone — restart would keep old argv.
  stop_session "$session_id" "$socket"
  return 1
}

cmd_reinit() {
  local name=$1
  [[ -n "$name" ]] || { echo "usage: reinit <role>" >&2; exit 1; }
  eval "$(resolve_role "$name")"
  if ! daemon_running "$ROLE_socket"; then
    start_daemon "$ROLE_socket"
  fi
  # Always drop + start with fleet.json command (agent_launch / runtime.command).
  # Never session.restart here — restart preserves the stored argv and was the
  # root cause of plain-pi Head sessions ignoring pi-head agent_launch.
  if session_exists "$ROLE_session_id" "$ROLE_socket"; then
    if ! remove_session "$ROLE_session_id" "$ROLE_socket"; then
      echo "warn: session.remove unavailable; restart may keep old command — upgrade vivi-pty" >&2
      restart_session "$ROLE_session_id" "$ROLE_socket" || true
    else
      start_session "$ROLE_session_id" "$ROLE_socket" "$ROLE_cwd" "$ROLE_driver" "${ROLE_command_args[@]}"
    fi
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
  status) [[ -n "$ROLE" ]] || usage; cmd_status "$ROLE" ;;
  doctor) cmd_doctor "$ROLE" ;;
  heal) cmd_heal "$ROLE" ;;
  reinit) [[ -n "$ROLE" ]] || usage; cmd_reinit "$ROLE" ;;
  "") usage ;;
  *) echo "unknown command: $COMMAND" >&2; usage ;;
esac
