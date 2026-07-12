#!/usr/bin/env bash
# opencode Hand control for fleet hand-N (fleet-agnostic).
# Set PROJECT and FLEET (or run from a fleet directory).
# Resolves tmux_target from fleet.json (legacy hand-1:1.1 or mgs:hand-1.1).
#
# Invariants:
#   - pane_pid MUST remain a shell (zsh/bash); opencode is always a child
#   - never `exec opencode`
#   - kill by ps -o comm= (macOS: command= is unreliable)
#   - kill -9 grandchildren before opencode parent
#   - launch with tmux send-keys -l (literal); wait ready before bootstrap
#
# Usage:
#   .vivi/opencode-hand-ctl.sh status   hand-1
#   .vivi/opencode-hand-ctl.sh classify hand-1
#   .vivi/opencode-hand-ctl.sh doctor            # fleet health + bag join (no kill)
#   .vivi/opencode-hand-ctl.sh doctor   hand-2
#   .vivi/opencode-hand-ctl.sh kill     hand-1
#   .vivi/opencode-hand-ctl.sh launch   hand-1
#   .vivi/opencode-hand-ctl.sh reinit   hand-1 --boot 'short pointer…'
#   .vivi/opencode-hand-ctl.sh reinit   hand-1 --no-boot
#   .vivi/opencode-hand-ctl.sh heal              # reinit unhealthy slots
#   .vivi/opencode-hand-ctl.sh heal     hand-3
#   .vivi/opencode-hand-ctl.sh topo     hand-1
#
# Env overrides: PROJECT, OPENCODE_BIN, TMUX_BIN, VIVI_BIN, PYTHON_BIN,
#                LOG, FORCE=1
# Requires: bash 3.2+, python3 >= 3.9. Portable macOS + Linux.
# Exit: 0 ok · 1 hard fail · 2 stuck-idle (ready but waiting) · 3 bad args
#       doctor: 0 healthy · 1 any slot unhealthy · 2 idle + open bag
#       heal:   0 all ok · 1 any reinit fail
set -euo pipefail

_FLEET_SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=lib/env.sh
. "$_FLEET_SCRIPT_DIR/lib/env.sh"
fleet_bootstrap_env

PROJECT="${PROJECT:-}"
if [[ -z "$PROJECT" ]]; then
  if [[ -n "${FLEET:-}" && -f "$FLEET" ]]; then
    PROJECT="$(CDPATH= cd -- "$(dirname "$FLEET")/.." && pwd)"
  else
    PROJECT="$(pwd)"
  fi
fi
FLEET="${FLEET:-$PROJECT/.vivi/fleet.json}"
TMUX_BIN="$(fleet_find_tmux 2>/dev/null || true)"; TMUX_BIN="${TMUX_BIN:-tmux}"
OPENCODE_BIN="$(fleet_find_bin opencode /opt/homebrew/bin/opencode /usr/local/bin/opencode "${HOME}/.local/bin/opencode" 2>/dev/null || true)"
OPENCODE_BIN="${OPENCODE_BIN:-opencode}"
PS_BIN="${PS_BIN:-$(fleet_find_bin ps /bin/ps || echo ps)}"
PYTHON_BIN="${PYTHON_BIN:-$(fleet_find_python3)}"
PGREP_BIN="${PGREP_BIN:-$(fleet_find_bin pgrep /usr/bin/pgrep /bin/pgrep || echo pgrep)}"

# Coreutils (BSD/GNU path variants)
HEAD_BIN="${HEAD_BIN:-$(fleet_find_bin head /usr/bin/head /bin/head || echo head)}"
TAIL_BIN="${TAIL_BIN:-$(fleet_find_bin tail /usr/bin/tail /bin/tail || echo tail)}"
GREP_BIN="${GREP_BIN:-$(fleet_find_bin grep /usr/bin/grep /bin/grep || echo grep)}"
MKDIR_BIN="${MKDIR_BIN:-$(fleet_find_bin mkdir /bin/mkdir /usr/bin/mkdir || echo mkdir)}"
DATE_BIN="${DATE_BIN:-$(fleet_find_bin date /bin/date /usr/bin/date || echo date)}"
LOG="${LOG:-/tmp/fleet-opencode-hand-ctl.log}"
WAIT_READY_SEC="${WAIT_READY_SEC:-30}"
__BAG_STATUS_CACHE=""

log() { printf '%s %s\n' "$($DATE_BIN -u +%H:%M:%S)" "$*" | tee -a "$LOG" >&2; }
die() { log "ERROR: $*"; exit 1; }

usage() {
  fleet_usage_from_header "$0" 2 30
  exit 3
}

need_bins() {
  [[ -x "$TMUX_BIN" ]] || TMUX_BIN="$(fleet_find_tmux)" || die "tmux missing"
  [[ -x "$OPENCODE_BIN" ]] || OPENCODE_BIN="$(fleet_find_bin opencode)" || die "opencode missing"
  [[ -x "$PS_BIN" ]] || die "ps missing: $PS_BIN"
  [[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$(fleet_find_python3)" || die "python3 missing"
  if [[ -z "${VIVI_BIN:-}" || ! -x "$VIVI_BIN" ]]; then
    VIVI_BIN="$(fleet_find_vivi 2>/dev/null || true)"
  fi
}

# --- pane utilities ---

pane_pid() {
  local target=$1
  "$TMUX_BIN" list-panes -t "$target" -F '#{pane_pid}' 2>/dev/null | "$HEAD_BIN" -1
}

pane_comm() {
  local pid=$1
  "$PS_BIN" -p "$pid" -o comm= 2>/dev/null || echo '?'
}

has_opencode_child() {
  local pid=$1 c
  for c in $("$PGREP_BIN" -P "$pid" 2>/dev/null || true); do
    if pane_comm "$c" | grep -qi opencode; then
      return 0
    fi
  done
  return 1
}

topo() {
  local target=$1
  local pid comm kids detail="" k
  if ! "$TMUX_BIN" has-session -t "${target%%:*}" 2>/dev/null; then
    log "topo $target NO_SESSION"
    return 1
  fi
  pid=$(pane_pid "$target") || return 1
  comm=$(pane_comm "$pid")
  kids=$("$PGREP_BIN" -P "$pid" 2>/dev/null | tr '\n' ' ' || true)
  for k in $kids; do
    detail+=" ${k}=$(pane_comm "$k")"
  done
  log "topo $target pane_pid=$pid pane_comm=$comm kids=[${kids}]${detail}"
}

capture_tail() {
  local target=$1
  local n=${2:-20}
  "$TMUX_BIN" capture-pane -t "$target" -p -S "-$n" 2>/dev/null | "$TAIL_BIN" -n "$n"
}

# --- classification ---

# Classes: running|idle_prompt|done_idle|error|down|unknown
# Uses opencode TUI markers matching fleet-sensors.py patterns:
#   idle:  "Ask anything..."
#   running: progress bar char (⬝), "Build ·", "esc interrupt", "Waiting for response"
#   done: completion indicators
#   error: error patterns
classify() {
  local target=$1
  local session=${target%%:*}
  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    echo down
    return 0
  fi
  local t
  t=$(capture_tail "$target" 22)

  # running — progress bar or active work
  if echo "$t" | "$GREP_BIN" -Eiq 'Working \(|Build ·|Build auto|esc to interrupt|Waiting for response'; then
    echo running
    return 0
  fi

  # error
  if echo "$t" | "$GREP_BIN" -Eiq 'error|failed|timed out|ECONNRESET|rate limit|over capacity'; then
    echo error
    return 0
  fi

  # idle — "Ask anything..." visible and no progress
  if echo "$t" | "$GREP_BIN" -Eiq 'Ask anything'; then
    if echo "$t" | "$GREP_BIN" -Eiq 'completed|done|finished'; then
      echo done_idle
      return 0
    fi
    echo idle_prompt
    return 0
  fi

  # opencode chrome present but unclear state
  if echo "$t" | "$GREP_BIN" -Eiq 'OpenCode Zen|ctrl\+p commands|Build ·'; then
    echo idle_prompt
    return 0
  fi

  echo unknown
}

classify_evidence() {
  local target=$1
  local class=$2
  local t line
  t=$(capture_tail "$target" 22)
  case "$class" in
    running)
      line=$(echo "$t" | "$GREP_BIN" -Ei 'Build ·|Build auto|esc to interrupt|Working' | "$TAIL_BIN" -1) ;;
    error)
      line=$(echo "$t" | "$GREP_BIN" -Ei 'error|failed|timed out|rate limit|capacity' | "$TAIL_BIN" -1) ;;
    idle_prompt)
      line=$(echo "$t" | "$GREP_BIN" -n 'Ask anything' | "$TAIL_BIN" -1) ;;
    done_idle)
      line=$(echo "$t" | "$GREP_BIN" -Ei 'completed|done|finished' | "$TAIL_BIN" -1) ;;
    down) line="no tmux session" ;;
    *) line=$(echo "$t" | "$TAIL_BIN" -3 | tr '\n' ' ' | cut -c1-120) ;;
  esac
  echo "${line:-"(no match line)"}" | tr -s '[:space:]' ' ' | cut -c1-160
}

ensure_session() {
  local session=$1 cwd=$2
  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    log "create session $session cwd=$cwd"
    "$TMUX_BIN" new-session -d -s "$session" -c "$cwd" -n main
    sleep 0.5
  fi
}

# --- kill ---

kill_opencode() {
  local target=$1 cwd=$2
  local pid c g ccomm
  pid=$(pane_pid "$target") || die "no pane $target"
  ccomm=$(pane_comm "$pid")
  log "kill_opencode $target pane_comm=$ccomm"

  if echo "$ccomm" | grep -qi opencode; then
    log "pane root is opencode — respawn shell"
    "$TMUX_BIN" respawn-pane -t "$target" -c "$cwd" -k -- /bin/zsh -l
    sleep 1
    return 0
  fi

  for c in $("$PGREP_BIN" -P "$pid" 2>/dev/null || true); do
    ccomm=$(pane_comm "$c")
    if echo "$ccomm" | grep -Eiq 'opencode'; then
      for g in $("$PGREP_BIN" -P "$c" 2>/dev/null || true); do
        log "  kill grandchild $g"
        kill -9 "$g" 2>/dev/null || true
      done
      log "  kill -9 $c ($ccomm)"
      kill -9 "$c" 2>/dev/null || true
    fi
  done
  sleep 0.5

  "$TMUX_BIN" send-keys -t "$target" C-c
  sleep 0.1
  "$TMUX_BIN" send-keys -t "$target" C-u
  sleep 0.1
  "$TMUX_BIN" send-keys -t "$target" Enter
  sleep 0.25

  local i
  for i in $(seq 1 12); do
    pid=$(pane_pid "$target")
    if ! has_opencode_child "$pid"; then
      log "no opencode child (attempt $i)"
      return 0
    fi
    for c in $("$PGREP_BIN" -P "$pid" 2>/dev/null || true); do
      if pane_comm "$c" | grep -qi opencode; then
        kill -9 "$c" 2>/dev/null || true
      fi
    done
    sleep 0.25
  done
  log "WARN: opencode child may remain"
  return 1
}

# --- launch ---

build_launch_cmd() {
  local cwd=$1 launch=$2
  local qcwd
  qcwd=$(printf '%s' "$cwd" | sed "s/'/'\\\\''/g")
  qcwd="'$qcwd'"
  if [[ -n "${launch// }" ]]; then
    launch="${launch#"${launch%%[![:space:]]*}"}"
    if [[ "$launch" == cd\ * ]]; then
      if [[ "$launch" == *"&&"* ]]; then
        launch="${launch#*&&}"
        launch="${launch#"${launch%%[![:space:]]*}"}"
      fi
    fi
    printf 'cd %s && { %s; }' "$qcwd" "$launch"
    return 0
  fi
  printf 'cd %s && %s --auto' "$qcwd" "$OPENCODE_BIN"
}

launch_opencode() {
  local target=$1 cwd=$2 launch=${3:-}
  local launch_cmd pid i t
  launch_cmd="$(build_launch_cmd "$cwd" "$launch")"
  log "launch: $launch_cmd"
  "$TMUX_BIN" send-keys -t "$target" -l -- "$launch_cmd"
  "$TMUX_BIN" send-keys -t "$target" Enter

  for i in $(seq 1 "$WAIT_READY_SEC"); do
    sleep 1
    pid=$(pane_pid "$target")
    t=$(capture_tail "$target" 16)

    if has_opencode_child "$pid"; then
      if echo "$t" | "$GREP_BIN" -Eiq 'OpenCode Zen|Build auto|Build ·|Ask anything'; then
        if echo "$(pane_comm "$pid")" | grep -Eiq 'zsh|bash'; then
          log "opencode ready after ${i}s (shell parent ok)"
          return 0
        fi
        log "WARN: opencode ready but pane root not shell: $(pane_comm "$pid")"
        return 0
      fi
    fi
  done
  log "FAIL launch after ${WAIT_READY_SEC}s"
  topo "$target"
  capture_tail "$target" 16 | tee -a "$LOG" >&2
  return 1
}

# --- bootstrap (wake pointer) ---

bootstrap() {
  local target=$1
  local msg=$2
  [[ -n "$msg" ]] || return 0
  log "bootstrap (${#msg} chars)"
  "$TMUX_BIN" send-keys -t "$target" -l -- "$msg"
  "$TMUX_BIN" send-keys -t "$target" Enter
  sleep 0.5
}

# --- bag helpers ---

bag_status_load() {
  if [[ -n "${__BAG_STATUS_CACHE}" ]]; then
    return 0
  fi
  if [[ -z "${VIVI_BIN}" || ! -x "$VIVI_BIN" ]]; then
    __BAG_STATUS_CACHE="__NO_VIVI__"
    return 0
  fi
  __BAG_STATUS_CACHE=$("$VIVI_BIN" mailspace status --project "$PROJECT" 2>/dev/null || echo "__VIVI_FAIL__")
}

bag_counts() {
  local name=$1
  bag_status_load
  if [[ "$__BAG_STATUS_CACHE" == "__NO_VIVI__" || "$__BAG_STATUS_CACHE" == "__VIVI_FAIL__" ]]; then
    printf '?\t?\t?\n'
    return 0
  fi
  BAG_STATUS_TEXT="$__BAG_STATUS_CACHE" "$PYTHON_BIN" - "$name" <<'PY'
import os, re, sys
name = sys.argv[1]
text = os.environ.get("BAG_STATUS_TEXT", "")
pat = re.compile(rf"^{re.escape(name)}\s+(\d+)\s+(\d+)\s+(\d+)\b", re.M)
m = pat.search(text)
if not m:
    print("?\t?\t?")
else:
    print(f"{m.group(1)}\t{m.group(2)}\t{m.group(3)}")
PY
}

bag_first_handle() {
  local name=$1
  local out
  if [[ -z "${VIVI_BIN}" || ! -x "$VIVI_BIN" ]]; then
    echo ""
    return 0
  fi
  out=$("$VIVI_BIN" board --project "$PROJECT" --for "$name" 2>/dev/null || true)
  BAG_BOARD_TEXT="$out" "$PYTHON_BIN" - <<'PY'
import os, re
text = os.environ.get("BAG_BOARD_TEXT", "")
for line in text.splitlines():
    m = re.match(r"\s+([0-9a-f]{7,})\s+", line)
    if m:
        print(m.group(1))
        break
PY
}

default_boot() {
  local name=$1
  local handle
  handle=$(bag_first_handle "$name")
  if [[ -n "$handle" ]]; then
    printf 'HAND WAKE %s. opencode. vivi --for %s --project %s. Show %s. Implement now.' \
      "$name" "$name" "$PROJECT" "$handle"
  else
    printf 'HAND WAKE %s. opencode. vivi --for %s --project %s. Show bag. Implement first open task now.' \
      "$name" "$name" "$PROJECT"
  fi
}

# --- fleet.json resolver ---

fleet_resolve() {
  local name=$1
  "$PYTHON_BIN" - "$FLEET" "$name" <<'PY'
import json, sys
fleet_path, name = sys.argv[1], sys.argv[2]
f = json.loads(open(fleet_path).read())
h = (f.get("hands") or {}).get(name)
if not h:
    sys.stderr.write(f"unknown hand in fleet: {name}\n")
    sys.exit(1)
session = h.get("tmux_session") or name
target = h.get("tmux_target") or f"{session}:1.1"
cwd = h.get("cwd") or f.get("project") or ""
if not cwd:
    sys.stderr.write("fleet hand missing cwd and fleet.project\n")
    sys.exit(1)
if h.get("packet") and isinstance(h["packet"], dict):
    cwd = h["packet"].get("worker_cwd") or h["packet"].get("root") or cwd
launch = h.get("agent_launch") or ""
print(f"{session}\t{cwd}\t{target}\t{launch}")
PY
}

# --- commands ---

cmd_status() {
  local name=$1
  local session cwd target launch
  IFS=$'\t' read -r session cwd target launch < <(fleet_resolve "$name")
  local class evidence pid
  class=$(classify "$target")
  evidence=$(classify_evidence "$target" "$class")
  pid=$(pane_pid "$target" 2>/dev/null || echo "?")
  printf 'SLOT %s  class=%s  target=%s  pid=%s  launch=%s\n' \
    "$name" "$class" "$target" "$pid" "$launch"
  printf '  evidence: %s\n' "$evidence"
}

opencode_hand_names() {
  "$PYTHON_BIN" - "$FLEET" <<'PY'
import json, sys
f = json.loads(open(sys.argv[1]).read())
for name, h in sorted((f.get("hands") or {}).items()):
    if (h.get("agent") or "") in ("opencode",):
        print(name)
PY
}

doctor_one() {
  local name=$1
  local verbose=${2:-0}
  local session cwd target launch
  local pid pcomm kids class evidence shell_ok=0 opencode_ok=0 cwd_ok=0 rec=""
  local bag_act bag_tasks bag_needs bag_note="" first_h=""
  __heal_needed=0
  IFS=$'\t' read -r session cwd target launch < <(fleet_resolve "$name")
  IFS=$'\t' read -r bag_act bag_tasks bag_needs < <(bag_counts "$name")

  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    printf 'SLOT %s  class=down  bag=%s/%s/%s  action=recreate+reinit  cwd=%s\n' \
      "$name" "$bag_act" "$bag_tasks" "$bag_needs" "$cwd"
    __doctor_rc=1
    __heal_needed=1
    return 0
  fi

  pid=$(pane_pid "$target")
  pcomm=$(pane_comm "$pid")
  kids=$("$PGREP_BIN" -P "$pid" 2>/dev/null | tr '\n' ' ' || true)
  path=$("$TMUX_BIN" display -p -t "$target" '#{pane_current_path}' 2>/dev/null || echo '?')
  class=$(classify "$target")
  evidence=$(classify_evidence "$target" "$class")

  echo "$pcomm" | grep -Eiq 'zsh|bash' && shell_ok=1
  has_opencode_child "$pid" && opencode_ok=1
  [[ "$path" == "$cwd" ]] && cwd_ok=1

  local bag_open=0 bag_tasks_open=0 bag_needs_only=0
  if [[ "$bag_act" != "?" && "$bag_act" -gt 0 ]]; then
    bag_open=1
    first_h=$(bag_first_handle "$name")
    bag_note="open_bag act=$bag_act tasks=$bag_tasks needs=$bag_needs${first_h:+ first=$first_h}"
    if [[ "$bag_tasks" != "?" && "$bag_tasks" -gt 0 ]]; then
      bag_tasks_open=1
    elif [[ "$bag_needs" != "?" && "$bag_needs" -gt 0 ]]; then
      bag_needs_only=1
    fi
  elif [[ "$bag_act" == "?" ]]; then
    bag_note="bag=unknown (vivi missing or parse fail)"
  else
    bag_note="bag empty"
  fi

  case "$class" in
    running)
      rec="ok (live turn)" ;;
    idle_prompt|done_idle)
      if [[ $bag_tasks_open -eq 1 ]]; then
        rec="STARVE: idle + open task -> reinit --boot (or: heal)"
        __doctor_rc=2
        __heal_needed=1
      elif [[ $bag_needs_only -eq 1 ]]; then
        rec="idle + needs-only (no auto-heal; Mind triage)"
      else
        rec="ok (idle + empty bag)"
      fi ;;
    error)
      rec="ACTION: reinit (model or connection error)"
      __doctor_rc=1
      __heal_needed=1 ;;
    down)
      rec="ACTION: recreate session + reinit"
      __doctor_rc=1
      __heal_needed=1 ;;
    unknown)
      rec="inspect pane; possible mid-start"
      if [[ ${__doctor_rc:-0} -eq 0 ]]; then __doctor_rc=1; fi
      if [[ $bag_tasks_open -eq 1 ]]; then __heal_needed=1; fi ;;
  esac

  if [[ $shell_ok -eq 0 ]]; then
    rec="ACTION: pane root not shell (respawn) - $rec"
    __doctor_rc=1
    __heal_needed=1
  fi
  if [[ $opencode_ok -eq 0 && "$class" != "down" ]]; then
    rec="ACTION: no opencode child - launch/reinit - $rec"
    __doctor_rc=1
    __heal_needed=1
  fi
  if [[ $cwd_ok -eq 0 ]]; then
    rec="NOTE: cwd drift pane!=fleet (launch cds) - $rec"
  fi

  printf 'SLOT %s  class=%-16s shell=%s opencode=%s cwd=%s\n' \
    "$name" "$class" \
    "$([[ $shell_ok -eq 1 ]] && echo ok || echo BAD)" \
    "$([[ $opencode_ok -eq 1 ]] && echo ok || echo MISSING)" \
    "$([[ $cwd_ok -eq 1 ]] && echo ok || echo DRIFT)"
  printf '      target=%s pane_pid=%s pane_comm=%s kids=[%s]\n' "$target" "$pid" "$pcomm" "$kids"
  printf '      path=%s\n' "$path"
  printf '      fleet=%s\n' "$cwd"
  printf '      bag: %s\n' "$bag_note"
  printf '      evidence: %s\n' "$evidence"
  printf '      rec: %s\n' "$rec"
  if [[ $__heal_needed -eq 1 ]]; then
    printf '      heal: yes\n'
  fi

  if [[ "$verbose" == "1" ]]; then
    echo "      ----- pane tail -----"
    capture_tail "$target" 14 | sed 's/^/      | /'
  fi
}

cmd_doctor() {
  local only="${1:-}"
  local verbose=0
  local names name
  local heal_list=""
  __doctor_rc=0
  __BAG_STATUS_CACHE=""

  if [[ -n "$only" ]]; then
    verbose=1
    names="$only"
  else
    names=$(opencode_hand_names)
  fi

  echo "=== opencode doctor  $($DATE_BIN -u +%Y-%m-%dT%H:%M:%SZ)  project=$PROJECT ==="
  echo "log=$LOG  vivi=${VIVI_BIN:-missing}"
  echo

  for name in $names; do
    doctor_one "$name" "$verbose"
    if [[ ${__heal_needed:-0} -eq 1 ]]; then
      heal_list="${heal_list}${heal_list:+ }$name"
    fi
    echo
  done

  if [[ -n "$heal_list" ]]; then
    echo "=== heal candidates ==="
    echo "  $heal_list"
    echo "  run: .vivi/opencode-hand-ctl.sh heal${only:+ $only}"
    echo
  fi

  return $__doctor_rc
}

cmd_kill() {
  local name=$1
  local session cwd target launch
  IFS=$'\t' read -r session cwd target launch < <(fleet_resolve "$name")
  log "KILL $name target=$target"
  kill_opencode "$target" "$cwd"
}

cmd_launch() {
  local name=$1
  local session cwd target launch
  IFS=$'\t' read -r session cwd target launch < <(fleet_resolve "$name")
  ensure_session "$session" "$cwd"
  log "LAUNCH $name target=$target cwd=$cwd"
  launch_opencode "$target" "$cwd" "$launch"
}

cmd_reinit() {
  local name=$1
  shift
  local boot="" boot_file="" no_boot=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --boot) fleet_need_optarg "$1" "${2-}"; boot="$2"; shift 2 ;;
      --boot-file) fleet_need_optarg "$1" "${2-}"; boot_file="$2"; shift 2 ;;
      --no-boot) no_boot=1; shift ;;
      *) die "unknown option: $1" ;;
    esac
  done

  local session cwd target launch
  IFS=$'\t' read -r session cwd target launch < <(fleet_resolve "$name")
  ensure_session "$session" "$cwd"

  log "REINIT $name target=$target"
  kill_opencode "$target" "$cwd" || log "kill exit=$? (continuing)"

  launch_opencode "$target" "$cwd" "$launch"
  local launch_rc=$?
  if [[ $launch_rc -ne 0 ]]; then
    log "FAIL reinit $name launch failed"
    return 1
  fi

  if [[ $no_boot -ne 1 ]]; then
    if [[ -z "$boot" && -n "$boot_file" ]]; then
      boot=$(cat "$boot_file" 2>/dev/null || true)
    fi
    if [[ -z "$boot" ]]; then
      boot=$(default_boot "$name")
    fi
    bootstrap "$target" "$boot"
  fi

  log "REINIT $name done"
  return 0
}

cmd_heal() {
  local only="${1:-}"
  local names name
  local healed=0 skipped=0 failed=0 rc=0
  __BAG_STATUS_CACHE=""

  if [[ -n "$only" ]]; then
    names="$only"
  else
    names=$(opencode_hand_names)
  fi

  echo "=== opencode heal  $($DATE_BIN -u +%Y-%m-%dT%H:%M:%SZ) ==="
  echo

  for name in $names; do
    __heal_needed=0
    doctor_one "$name" "0"
    if [[ ${__heal_needed:-0} -eq 0 ]]; then
      echo "  SKIP $name (healthy)"
      skipped=$((skipped + 1))
      continue
    fi

    boot=$(default_boot "$name")
    echo "  HEAL $name -> reinit"
    log "HEAL $name boot=${boot:0:120}"
    set +e
    cmd_reinit "$name" --boot "$boot"
    local r=$?
    set -e
    if [[ $r -eq 0 ]]; then
      healed=$((healed + 1))
    else
      failed=$((failed + 1))
      [[ $rc -eq 0 ]] && rc=1
    fi
    echo
  done

  log "HEAL done healed=$healed skipped=$skipped failed=$failed"
  echo "heal_summary healed=$healed skipped=$skipped failed=$failed exit=$rc"
  return $rc
}

# --- main ---
need_bins
: >>"$LOG"
cmd=${1:-}
shift || true
case "$cmd" in
  status) [[ $# -ge 1 ]] || usage; cmd_status "$1" ;;
  classify)
    [[ $# -ge 1 ]] || usage
    IFS=$'\t' read -r session cwd target launch < <(fleet_resolve "$1")
    echo "$(classify "$target")"
    ;;
  doctor|probe|debug)
    cmd_doctor "${1:-}" ;;
  kill) [[ $# -ge 1 ]] || usage; cmd_kill "$1" ;;
  launch) [[ $# -ge 1 ]] || usage; cmd_launch "$1" ;;
  reinit) [[ $# -ge 1 ]] || usage; cmd_reinit "$@" ;;
  heal)
    cmd_heal "${1:-}" ;;
  topo)
    [[ $# -ge 1 ]] || usage
    IFS=$'\t' read -r session cwd target launch < <(fleet_resolve "$1")
    topo "$target"
    ;;
  -h|--help|help|"") usage ;;
  *) die "unknown command: $cmd" ;;
esac
