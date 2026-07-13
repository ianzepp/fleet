#!/usr/bin/env bash
# Generic Codex reinit for fleet hand-N (fleet-agnostic).
# Set PROJECT and FLEET_FILE (or run from a fleet with fleet JSON).
# Resolves the logical role through fleet-resolve.py.
#
# Invariants:
#   - pane_pid MUST remain a shell (zsh/bash); codex is always a child
#   - never `exec codex`
#   - kill by ps -o comm= (macOS: command= is unreliable)
#   - kill -9 grandchildren before codex parent
#   - launch with tmux send-keys -l (literal); wait ready before bootstrap
#   - after bootstrap, require Working (or exit STUCK_IDLE)
#
# Usage:
#   .vivi/codex-reinit.sh status   --role hand-1
#   .vivi/codex-reinit.sh classify --role hand-1
#   .vivi/codex-reinit.sh doctor            # fleet health + bag join (no kill)
#   .vivi/codex-reinit.sh doctor   --role hand-2 # one slot, verbose evidence
#   .vivi/codex-reinit.sh probe    --role hand-1 # same as doctor one-slot
#   .vivi/codex-reinit.sh snapshot [--role hand-N] # forensic dump under /tmp/codex-debug-*
#   .vivi/codex-reinit.sh heal              # reinit idle/error + open bag (leave running)
#   .vivi/codex-reinit.sh heal     --role hand-3 # one slot only
#   .vivi/codex-reinit.sh reinit   --role hand-1 --boot 'short pointer…'
#   .vivi/codex-reinit.sh reinit   --role hand-2 --boot-file /tmp/boot.txt
#   .vivi/codex-reinit.sh reinit   --role hand-3 --no-boot
#   .vivi/codex-reinit.sh reinit-all --boot-template 'HAND WAKE {name}. vivi --for {name}. Implement open bag now.'
#
# Env overrides: PROJECT, CODEX_BIN, TMUX_BIN, VIVI_BIN, PYTHON_BIN, MODEL,
#                CODEX_EFFORT, LOG, FORCE=1
# Launch: prefers fleet hand agent_launch when set; else synthesizes
#   cd <cwd> && $CODEX_BIN -m <model> -c model_reasoning_effort=<effort>
# Default effort for synthesized launch: CODEX_EFFORT or xhigh (Hand preferred).
# Requires: bash 3.2+, python3 >= 3.9. Portable macOS + Linux.
# Exit: 0 ok · 1 hard fail · 2 stuck-idle (ready but never Working) · 3 bad args
#       doctor: 0 healthy · 1 any slot unhealthy · 2 trust/stuck/starving needing action
#       heal:   0 all ok · 1 any reinit fail · 2 any stuck_idle
set -euo pipefail

_FLEET_SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=lib/env.sh
. "$_FLEET_SCRIPT_DIR/lib/env.sh"
fleet_bootstrap_env

PROJECT="${PROJECT:-}"
if [[ -z "$PROJECT" ]]; then
  if [[ -n "${FLEET_FILE:-}" && -f "$FLEET_FILE" ]]; then
    PROJECT="$(CDPATH= cd -- "$(dirname "$FLEET_FILE")/.." && pwd)"
  else
    PROJECT="$(pwd)"
  fi
fi
FLEET_ID="${FLEET_ID:-}"
FLEET_FILE="${FLEET_FILE:-}"
RUNTIME_TARGET="${RUNTIME_TARGET:-}"
TMUX_BIN="$(fleet_find_tmux 2>/dev/null || true)"; TMUX_BIN="${TMUX_BIN:-tmux}"
CODEX_BIN="$(fleet_find_bin codex /opt/homebrew/bin/codex /usr/local/bin/codex "${HOME}/.local/bin/codex" 2>/dev/null || true)"
CODEX_BIN="${CODEX_BIN:-codex}"
VIVI_BIN="$(fleet_find_vivi 2>/dev/null || true)"
PS_BIN="${PS_BIN:-$(fleet_find_bin ps /bin/ps /usr/bin/ps || echo /bin/ps)}"
PGREP_BIN="${PGREP_BIN:-$(fleet_find_bin pgrep /usr/bin/pgrep /bin/pgrep || echo /usr/bin/pgrep)}"
if ! PYTHON_BIN="$(fleet_find_python3)"; then
  echo "ERROR: python3 >= 3.9 not found (set PYTHON_BIN)" >&2
  exit 3
fi
# Coreutils (BSD/GNU path variants)
HEAD_BIN="${HEAD_BIN:-$(fleet_find_bin head /usr/bin/head /bin/head || echo head)}"
TAIL_BIN="${TAIL_BIN:-$(fleet_find_bin tail /usr/bin/tail /bin/tail || echo tail)}"
GREP_BIN="${GREP_BIN:-$(fleet_find_bin grep /usr/bin/grep /bin/grep || echo grep)}"
MKDIR_BIN="${MKDIR_BIN:-$(fleet_find_bin mkdir /bin/mkdir /usr/bin/mkdir || echo mkdir)}"
DATE_BIN="${DATE_BIN:-$(fleet_find_bin date /bin/date /usr/bin/date || echo date)}"
LOG="${LOG:-/tmp/fleet-codex-reinit.log}"
MODEL="${MODEL:-}"                 # empty → fleet agent_model (or --model on reinit)
CODEX_EFFORT="${CODEX_EFFORT:-}"   # empty → xhigh when synthesizing (Hand preferred)
WAIT_READY_SEC="${WAIT_READY_SEC:-45}"
WAIT_WORKING_SEC="${WAIT_WORKING_SEC:-90}"
WAIT_SETTLE_SEC="${WAIT_SETTLE_SEC:-8}"
AUTO_TRUST="${AUTO_TRUST:-1}"      # accept trust UI during launch
__BAG_STATUS_CACHE=""              # vivi mailspace status text (doctor/heal)

log() { printf '%s %s\n' "$($DATE_BIN -u +%H:%M:%S)" "$*" | tee -a "$LOG" >&2; }

die() { log "ERROR: $*"; exit 1; }

usage() {
  fleet_usage_from_header "$0" 2 30
  exit 3
}

need_bins() {
  [[ -x "$TMUX_BIN" ]] || TMUX_BIN="$(fleet_find_tmux)" || die "tmux missing"
  [[ -x "$CODEX_BIN" ]] || CODEX_BIN="$(fleet_find_bin codex)" || die "codex missing"
  [[ -x "$PS_BIN" ]] || die "ps missing: $PS_BIN"
  [[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$(fleet_find_python3)" || die "python3 missing"
  if [[ -z "${VIVI_BIN:-}" || ! -x "$VIVI_BIN" ]]; then
    VIVI_BIN="$(fleet_find_vivi 2>/dev/null || true)"
  fi
}

# Load once: full `vivi mailspace status` for bag join.
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

# Prints: actionable\ttasks\tneeds  (or ?\t?\t? if unknown)
bag_counts() {
  local name=$1
  bag_status_load
  if [[ "$__BAG_STATUS_CACHE" == "__NO_VIVI__" || "$__BAG_STATUS_CACHE" == "__VIVI_FAIL__" ]]; then
    printf '?\t?\t?\n'
    return 0
  fi
  # Pass status via env — do not pipe + heredoc (heredoc steals stdin).
  BAG_STATUS_TEXT="$__BAG_STATUS_CACHE" "$PYTHON_BIN" - "$name" <<'PY'
import os, re, sys
name = sys.argv[1]
text = os.environ.get("BAG_STATUS_TEXT", "")
# identity  actionable  tasks open  needs open  ...
pat = re.compile(rf"^{re.escape(name)}\s+(\d+)\s+(\d+)\s+(\d+)\b", re.M)
m = pat.search(text)
if not m:
    print("?\t?\t?")
else:
    print(f"{m.group(1)}\t{m.group(2)}\t{m.group(3)}")
PY
}

# First open task or need handle (short), empty if none / vivi missing.
bag_first_handle() {
  local name=$1
  local out
  if [[ -z "${VIVI_BIN}" || ! -x "$VIVI_BIN" ]]; then
    echo ""
    return 0
  fi
  out=$("$VIVI_BIN" board --project "$PROJECT" --for "$name" 2>/dev/null || true)
  # Env again — avoid pipe+heredoc stdin clash.
  BAG_BOARD_TEXT="$out" "$PYTHON_BIN" - <<'PY'
import os, re
text = os.environ.get("BAG_BOARD_TEXT", "")
# lines like: "  ea00ac1  2026-07-11T...  hand-1@...  P2 task: ..."
for line in text.splitlines():
    m = re.match(r"\s+([0-9a-f]{7,})\s+", line)
    if m:
        print(m.group(1))
        break
PY
}

# Default short bootstrap for heal/reinit when Mind did not supply --boot.
default_boot() {
  local name=$1
  local handle
  handle=$(bag_first_handle "$name")
  if [[ -n "$handle" ]]; then
    printf 'HAND WAKE %s. Codex. vivi --for %s --project %s. Show %s. Implement now.' \
      "$name" "$name" "$PROJECT" "$handle"
  else
    printf 'HAND WAKE %s. Codex. vivi --for %s --project %s. Show bag. Implement first open task now.' \
      "$name" "$name" "$PROJECT"
  fi
}

# Resolve hand fields from fleet JSON (canonical: hands; legacy: hands).
# Prints: session\tcwd\ttarget\tmodel\tlaunch
fleet_resolve() {
  local name=$1
  local resolver=("$PYTHON_BIN" "$_FLEET_SCRIPT_DIR/fleet-resolve.py"
    --project "$PROJECT" --fleet-file "$FLEET_FILE" --role "$name" --json)
  [[ -n "$FLEET_ID" ]] && resolver+=(--fleet "$FLEET_ID")
  [[ -n "$RUNTIME_TARGET" ]] && resolver+=(--runtime-target "$RUNTIME_TARGET")
  "${resolver[@]}" | "$PYTHON_BIN" -c '
import json, sys
x = json.load(sys.stdin)
print("\t".join(str(x.get(k, "")) for k in ("session", "cwd", "target", "model", "launch")))
'
}

pane_pid() {
  local target=$1
  "$TMUX_BIN" list-panes -t "$target" -F '#{pane_pid}' 2>/dev/null | "$HEAD_BIN" -1
}

pane_comm() {
  local pid=$1
  "$PS_BIN" -p "$pid" -o comm= 2>/dev/null || echo '?'
}

has_codex_child() {
  local pid=$1 c
  for c in $("$PGREP_BIN" -P "$pid" 2>/dev/null || true); do
    if pane_comm "$c" | grep -qi codex; then
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

# True when pane shows Codex workspace-trust modal (blocks ready chrome).
has_trust_ui() {
  local t=$1
  echo "$t" | "$GREP_BIN" -Eiq 'Yes, continue|Do you trust|trust this workspace|No, quit|Press enter to continue|Always allow|Allow always|Allow once|until OpenCode is restarted'
}

# Accept trust modal: prefer "1" (Yes) then Enter; also bare Enter for "Press enter".
accept_trust_ui() {
  local target=$1
  log "trust UI → send 1 + Enter"
  "$TMUX_BIN" send-keys -t "$target" -l -- '1'
  "$TMUX_BIN" send-keys -t "$target" Enter
  sleep 0.6
  local t
  t=$(capture_tail "$target" 12)
  if has_trust_ui "$t"; then
    log "trust UI still up → bare Enter"
    "$TMUX_BIN" send-keys -t "$target" Enter
    sleep 0.5
  fi
}

# Classify last ~20 lines.
# Classes: running|idle_prompt|done_idle|trust_prompt|error_capacity|error_connection|down|unknown
#
# Order matters: live Working beats tool-output noise (e.g. `timeout 1800 …`,
# `error: test failed`). Connection errors must not match bare shell `timeout`.
classify() {
  local target=$1
  local session=${target%%:*}
  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    echo down
    return 0
  fi
  local t
  t=$(capture_tail "$target" 22)

  # Live turn first — tool scrollback often contains "error:" / "timeout" tokens.
  if echo "$t" | "$GREP_BIN" -Eiq 'Working \(|esc to interrupt|Waiting for response'; then
    echo running
    return 0
  fi
  if has_trust_ui "$t"; then
    echo trust_prompt
    return 0
  fi
  if echo "$t" | "$GREP_BIN" -Eiq 'over capacity|rate limit|[^0-9]429[^0-9]|usage limit hard|try again later'; then
    echo error_capacity
    return 0
  fi
  # Narrow: do NOT match GNU `timeout N cmd` in tool traces.
  if echo "$t" | "$GREP_BIN" -Eiq 'ECONNRESET|connection failed|connection error|connect timed out|request timed out|stream timed out|network timeout|TLS handshake timeout|websocket.*timeout'; then
    echo error_connection
    return 0
  fi
  # settled codex chrome with ›
  if echo "$t" | "$GREP_BIN" -q '›'; then
    if echo "$t" | "$GREP_BIN" -Eiq 'bag empty|standing by|turn end|Turn completed|ready-to-merge'; then
      echo done_idle
      return 0
    fi
    echo idle_prompt
    return 0
  fi
  echo unknown
}

# One-line evidence why class was chosen (for doctor).
classify_evidence() {
  local target=$1
  local class=$2
  local t line
  t=$(capture_tail "$target" 22)
  case "$class" in
    running)
      line=$(echo "$t" | "$GREP_BIN" -Ei 'Working \(|esc to interrupt|Waiting for response' | "$TAIL_BIN" -1)
      ;;
    trust_prompt)
      line=$(echo "$t" | "$GREP_BIN" -Ei 'Yes, continue|Do you trust|trust this|No, quit|Press enter to continue|Always allow|Allow always|Allow once|until OpenCode is restarted' | "$HEAD_BIN" -1)
      ;;
    error_capacity)
      line=$(echo "$t" | "$GREP_BIN" -Ei 'over capacity|rate limit|429|usage limit' | "$TAIL_BIN" -1)
      ;;
    error_connection)
      line=$(echo "$t" | "$GREP_BIN" -Ei 'ECONNRESET|connection failed|connection error|timed out|timeout' | "$TAIL_BIN" -1)
      ;;
    done_idle)
      line=$(echo "$t" | "$GREP_BIN" -Ei 'bag empty|standing by|turn end|ready-to-merge' | "$TAIL_BIN" -1)
      ;;
    idle_prompt)
      line=$(echo "$t" | "$GREP_BIN" -n '›' | "$TAIL_BIN" -1)
      ;;
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

kill_codex() {
  local target=$1 cwd=$2
  local pid c g ccomm
  pid=$(pane_pid "$target") || die "no pane $target"
  ccomm=$(pane_comm "$pid")
  log "kill_codex $target pane_comm=$ccomm"

  if echo "$ccomm" | grep -qi codex; then
    log "pane root is codex — respawn shell"
    "$TMUX_BIN" respawn-pane -t "$target" -c "$cwd" -k -- /bin/zsh -l
    sleep 1
    return 0
  fi

  # also kill grok if migrating
  for c in $("$PGREP_BIN" -P "$pid" 2>/dev/null || true); do
    ccomm=$(pane_comm "$c")
    if echo "$ccomm" | grep -Eiq 'codex|grok'; then
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

  # drain remaining codex children
  local i
  for i in $(seq 1 12); do
    pid=$(pane_pid "$target")
    if ! has_codex_child "$pid"; then
      log "no codex child (attempt $i)"
      return 0
    fi
    for c in $("$PGREP_BIN" -P "$pid" 2>/dev/null || true); do
      if pane_comm "$c" | grep -qi codex; then
        kill -9 "$c" 2>/dev/null || true
      fi
    done
    sleep 0.25
  done
  log "WARN: codex child may remain"
  return 1
}

# Build pane launch line: prefer fleet agent_launch; else codex -m + effort.
# Always cd to fleet cwd first so packet rehomes stick even if launch omits cd.
build_launch_cmd() {
  local cwd=$1 model=$2 launch=$3
  local effort qcwd
  # portable enough quote for spaces (no newlines expected in cwd)
  qcwd=$(printf '%s' "$cwd" | sed "s/'/'\\\\''/g")
  qcwd="'$qcwd'"
  if [[ -n "${launch// }" ]]; then
    # Honor fleet agent_launch (flags, wrappers, effort, auth env).
    # Strip a leading "cd … &&" so fleet cwd wins; wrap so "a; b" still runs under cd.
    launch="${launch#"${launch%%[![:space:]]*}"}" # ltrim
    if [[ "$launch" == cd\ * ]]; then
      if [[ "$launch" == *"&&"* ]]; then
        launch="${launch#*&&}"
        launch="${launch#"${launch%%[![:space:]]*}"}"
      fi
    fi
    printf 'cd %s && { %s; }' "$qcwd" "$launch"
    return 0
  fi
  effort="${CODEX_EFFORT:-xhigh}"
  # Match preferred Hand effort; operators set agent_launch for non-defaults.
  printf 'cd %s && %s -m %s -c model_reasoning_effort=%s' \
    "$qcwd" "$CODEX_BIN" "$model" "$effort"
}

launch_codex() {
  local target=$1 cwd=$2 model=$3 launch=${4:-}
  local launch_cmd pid i t trusted=0
  launch_cmd="$(build_launch_cmd "$cwd" "$model" "$launch")"
  log "launch: $launch_cmd"
  "$TMUX_BIN" send-keys -t "$target" -l -- "$launch_cmd"
  "$TMUX_BIN" send-keys -t "$target" Enter

  for i in $(seq 1 "$WAIT_READY_SEC"); do
    sleep 1
    pid=$(pane_pid "$target")
    t=$(capture_tail "$target" 16)

    # Trust modal blocks ready chrome — auto-accept once (or twice if stubborn).
    if [[ "$AUTO_TRUST" == "1" ]] && has_trust_ui "$t"; then
      if [[ $trusted -lt 2 ]]; then
        accept_trust_ui "$target"
        trusted=$((trusted + 1))
        continue
      fi
      log "FAIL launch: trust UI still up after auto-accept"
      capture_tail "$target" 14 | tee -a "$LOG" >&2
      return 1
    fi

    if has_codex_child "$pid"; then
      # ready: codex chrome present (› / model line), not trust modal
      if echo "$t" | grep -Eiq 'gpt-5|OpenAI Codex|model_reasoning|›'; then
        if ! has_trust_ui "$t"; then
          if echo "$(pane_comm "$pid")" | grep -Eiq 'zsh|bash'; then
            log "codex ready after ${i}s (shell parent ok)"
            return 0
          fi
          log "WARN: codex ready but pane root not shell: $(pane_comm "$pid")"
          return 0
        fi
      fi
    fi
  done
  log "FAIL launch after ${WAIT_READY_SEC}s"
  topo "$target"
  capture_tail "$target" 16 | tee -a "$LOG" >&2
  return 1
}

bootstrap() {
  local target=$1
  local msg=$2
  [[ -n "$msg" ]] || return 0
  log "bootstrap (${#msg} chars)"
  "$TMUX_BIN" send-keys -t "$target" -l -- "$msg"
  "$TMUX_BIN" send-keys -t "$target" Enter
  sleep 0.4
  # one more Enter only if still looks unsubmitted (heuristic: no Working yet and last line is input)
  local t
  t=$(capture_tail "$target" 8)
  if ! echo "$t" | grep -Eiq 'Working \(|esc to interrupt'; then
    # small settle — do not thrash Enter (can submit empty turns)
    sleep 0.5
  fi
}

# After bootstrap: want Working. Stuck-idle = settled › without Working for WAIT_WORKING_SEC.
wait_working_or_stuck() {
  local target=$1
  local i t class saw_working=0
  for i in $(seq 1 "$WAIT_WORKING_SEC"); do
    sleep 1
    t=$(capture_tail "$target" 18)
    if echo "$t" | grep -Eiq 'Working \(|esc to interrupt'; then
      log "Working observed after ${i}s"
      return 0
    fi
    if echo "$t" | grep -Eiq 'over capacity|rate limit|429'; then
      log "capacity error while waiting"
      return 1
    fi
    # after settle window, idle › without working → stuck
    if [ "$i" -ge "$WAIT_SETTLE_SEC" ]; then
      class=$(classify "$target")
      if [[ "$class" == "idle_prompt" || "$class" == "done_idle" ]]; then
        # still early — keep waiting until WAIT_WORKING
        :
      fi
    fi
  done
  class=$(classify "$target")
  log "STUCK_IDLE class=$class after ${WAIT_WORKING_SEC}s (no Working)"
  capture_tail "$target" 16 | tee -a "$LOG" >&2
  return 2
}

cmd_status() {
  local name=$1
  local session cwd target model launch
  IFS=$'\t' read -r session cwd target model launch < <(fleet_resolve "$name")
  echo "hand=$name session=$session target=$target cwd=$cwd model=$model"
  echo "launch=${launch:-"(template codex -m $model)"}"
  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    echo "class=down"
    return 0
  fi
  topo "$target" || true
  echo "class=$(classify "$target")"
  echo "----- pane tail -----"
  capture_tail "$target" 12
}

cmd_reinit() {
  local name=$1
  shift
  local boot="" no_boot=0 wait_work=1
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --boot) boot=$2; shift 2 ;;
      --boot-file) boot=$(cat "$2"); shift 2 ;;
      --no-boot) no_boot=1; shift ;;
      --no-wait-working) wait_work=0; shift ;;
      --model) MODEL=$2; shift 2 ;;
      *) die "unknown arg: $1" ;;
    esac
  done

  local session cwd target model launch
  IFS=$'\t' read -r session cwd target model launch < <(fleet_resolve "$name")
  [[ -n "$MODEL" ]] && model="$MODEL"
  # --model override: synthesize from MODEL (ignore agent_launch model flags)
  if [[ -n "$MODEL" ]]; then
    log "MODEL override=$MODEL (using synthesized launch, not agent_launch)"
    launch=""
  fi

  log "======== REINIT $name ========"
  log "session=$session target=$target cwd=$cwd model=$model launch=${launch:-"(synthesize)"}"

  # refuse to kill mid-flight unless FORCE=1
  if "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    local cls
    cls=$(classify "$target")
    if [[ "$cls" == "running" && "${FORCE:-0}" != "1" ]]; then
      log "REFUSE: $name is running (set FORCE=1 to override)"
      echo "refused_running" >&2
      return 1
    fi
  fi

  ensure_session "$session" "$cwd"
  # fix cwd if pane drifted
  local path
  path=$("$TMUX_BIN" display -p -t "$target" '#{pane_current_path}' 2>/dev/null || true)
  if [[ -n "$path" && "$path" != "$cwd" ]]; then
    log "cwd drift pane=$path fleet=$cwd (launch will cd)"
  fi

  kill_codex "$target" "$cwd" || true
  topo "$target" || true
  launch_codex "$target" "$cwd" "$model" "$launch" || return 1
  topo "$target" || true

  if [[ "$no_boot" -eq 0 && -n "$boot" ]]; then
    bootstrap "$target" "$boot"
    if [[ "$wait_work" -eq 1 ]]; then
      set +e
      wait_working_or_stuck "$target"
      local rc=$?
      set -e
      if [[ $rc -eq 2 ]]; then
        echo "stuck_idle $name"
        return 2
      fi
      if [[ $rc -ne 0 ]]; then
        return 1
      fi
    fi
  fi

  echo "ok $name class=$(classify "$target")"
  return 0
}

cmd_reinit_all() {
  local template="" wait_flag=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --boot-template) template=$2; shift 2 ;;
      --no-wait-working) wait_flag=(--no-wait-working); shift ;;
      *) die "unknown arg: $1" ;;
    esac
  done
  [[ -n "$template" ]] || template='HAND WAKE {name}. Codex. vivi --for {name} --project {project}. Show bag. Implement first open task now.'

  local names rc=0 name boot
  names=$(fleet_roles)
  local fails=0 stuck=0
  for name in $names; do
    boot=${template//\{name\}/$name}
    boot=${boot//\{project\}/$PROJECT}
    set +e
    cmd_reinit "$name" --boot "$boot" "${wait_flag[@]}"
    local r=$?
    set -e
    if [[ $r -eq 2 ]]; then stuck=$((stuck + 1)); rc=2
    elif [[ $r -ne 0 ]]; then fails=$((fails + 1)); rc=1
    fi
  done
  log "reinit-all done fails=$fails stuck=$stuck"
  return $rc
}

codex_hand_names() {
  fleet_roles
}

fleet_roles() {
  local resolver=("$PYTHON_BIN" "$_FLEET_SCRIPT_DIR/fleet-resolve.py"
    --project "$PROJECT" --fleet-file "$FLEET_FILE" --list --agent codex --group hand)
  [[ -n "$FLEET_ID" ]] && resolver+=(--fleet "$FLEET_ID")
  "${resolver[@]}"
}

# Per-slot health snapshot (stdout). Sets global __doctor_rc: 0 ok · 1 bad · 2 action.
# Sets __heal_needed=1 when heal should reinit this slot.
doctor_one() {
  local name=$1
  local verbose=${2:-0}
  local session cwd target model launch
  local pid pcomm kids path class evidence shell_ok=0 codex_ok=0 cwd_ok=0 rec=""
  local bag_act bag_tasks bag_needs bag_note="" first_h=""
  __heal_needed=0
  IFS=$'\t' read -r session cwd target model launch < <(fleet_resolve "$name")
  IFS=$'\t' read -r bag_act bag_tasks bag_needs < <(bag_counts "$name")

  if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
    printf 'SLOT %s  class=down  bag=%s/%s/%s  action=recreate+reinit  model=%s  cwd=%s\n' \
      "$name" "$bag_act" "$bag_tasks" "$bag_needs" "$model" "$cwd"
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
  has_codex_child "$pid" && codex_ok=1
  [[ "$path" == "$cwd" ]] && cwd_ok=1

  # Bag join: open *tasks* starve idle codex. Needs-only may be hold/decision
  # (env gate) — note but do not auto-heal thrash.
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
      rec="ok (live turn)"
      ;;
    idle_prompt|done_idle)
      if [[ $bag_tasks_open -eq 1 ]]; then
        rec="STARVE: idle/done + open task → reinit --boot (or: heal)"
        __doctor_rc=2
        __heal_needed=1
      elif [[ $bag_needs_only -eq 1 ]]; then
        rec="idle + needs-only (no auto-heal; Mind triage hold vs implementable)"
        # action note only — do not thrash reinit on env-gated needs
      else
        rec="ok (idle + empty bag — Mind should refill map if not pause)"
      fi
      ;;
    trust_prompt)
      rec="ACTION: accept trust (script auto on reinit) or send 1+Enter"
      __doctor_rc=2
      __heal_needed=1
      ;;
    error_capacity)
      rec="ACTION: model fallback then reinit"
      __doctor_rc=1
      __heal_needed=1
      ;;
    error_connection)
      rec="ACTION: reinit same model; if red → capacity path"
      __doctor_rc=1
      __heal_needed=1
      ;;
    down)
      rec="ACTION: recreate session + reinit"
      __doctor_rc=1
      __heal_needed=1
      ;;
    unknown)
      rec="inspect pane; possible mid-start — snapshot then reinit if stuck"
      if [[ ${__doctor_rc:-0} -eq 0 ]]; then __doctor_rc=1; fi
      if [[ $bag_tasks_open -eq 1 ]]; then __heal_needed=1; fi
      ;;
  esac

  if [[ $shell_ok -eq 0 ]]; then
    rec="ACTION: pane root not shell (respawn) — $rec"
    __doctor_rc=1
    __heal_needed=1
  fi
  if [[ $codex_ok -eq 0 && "$class" != "down" ]]; then
    rec="ACTION: no codex child — launch/reinit — $rec"
    __doctor_rc=1
    __heal_needed=1
  fi
  if [[ $cwd_ok -eq 0 ]]; then
    rec="NOTE: cwd drift pane≠fleet (launch cds) — $rec"
  fi

  printf 'SLOT %s  class=%-16s shell=%s codex=%s cwd=%s model=%s\n' \
    "$name" "$class" \
    "$([[ $shell_ok -eq 1 ]] && echo ok || echo BAD)" \
    "$([[ $codex_ok -eq 1 ]] && echo ok || echo MISSING)" \
    "$([[ $cwd_ok -eq 1 ]] && echo ok || echo DRIFT)" \
    "$model"
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
  __BAG_STATUS_CACHE="" # fresh bag read each doctor

  if [[ -n "$only" ]]; then
    verbose=1
    names="$only"
  else
    names=$(codex_hand_names)
  fi

  echo "=== codex doctor  $($DATE_BIN -u +%Y-%m-%dT%H:%M:%SZ)  project=$PROJECT ==="
  echo "log=$LOG  AUTO_TRUST=$AUTO_TRUST  vivi=${VIVI_BIN:-missing}"
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
    echo "  run: .vivi/codex-reinit.sh heal${only:+ $only}"
    echo
  fi

  # Recent reinit log signal (last 200 lines of log)
  if [[ -f "$LOG" ]]; then
    echo "=== recent reinit log (last matches) ==="
    "$GREP_BIN" -E 'REINIT |Working observed|STUCK_IDLE|FAIL launch|REFUSE:|trust UI|reinit-all done|HEAL ' "$LOG" \
      | "$TAIL_BIN" -20 || echo "(no matches)"
    echo
    local stuck fail refuse
    # grep -c exits 1 on zero matches — do not append a second "0" via || echo.
    stuck=$("$GREP_BIN" -c 'STUCK_IDLE' "$LOG" 2>/dev/null || true)
    fail=$("$GREP_BIN" -c 'FAIL launch' "$LOG" 2>/dev/null || true)
    refuse=$("$GREP_BIN" -c 'REFUSE:' "$LOG" 2>/dev/null || true)
    echo "log_totals stuck_idle=${stuck:-0} fail_launch=${fail:-0} refuse_running=${refuse:-0}"
  fi

  echo
  echo "doctor_exit=$__doctor_rc  (0 healthy · 1 unhealthy · 2 trust/stuck/starving action)"
  return "$__doctor_rc"
}

# Forensic dump for one or all codex hands — no kill.
cmd_snapshot() {
  local only="${1:-}"
  local names name
  local stamp dir slot_dir
  stamp=$($DATE_BIN -u +%Y%m%dT%H%M%SZ)
  dir="/tmp/codex-debug-${stamp}"
  "$MKDIR_BIN" -p "$dir"

  if [[ -n "$only" ]]; then
    names="$only"
  else
    names=$(codex_hand_names)
  fi

  {
    echo "project=$PROJECT"
    echo "stamp=$stamp"
    echo "codex=$($CODEX_BIN --version 2>&1 | head -3 || true)"
    echo "tmux=$($TMUX_BIN -V 2>&1 || true)"
    echo "vivi=${VIVI_BIN:-missing}"
    echo "AUTO_TRUST=$AUTO_TRUST"
  } >"$dir/meta.txt"

  cp "$FLEET_FILE" "$dir/fleet.json" 2>/dev/null || true
  if [[ -x "${VIVI_BIN:-}" ]]; then
    "$VIVI_BIN" mailspace status --project "$PROJECT" >"$dir/mailspace-status.txt" 2>&1 || true
  fi
  if [[ -f "$LOG" ]]; then
    "$TAIL_BIN" -200 "$LOG" >"$dir/reinit-log-tail.txt"
  fi

  for name in $names; do
    slot_dir="$dir/$name"
    "$MKDIR_BIN" -p "$slot_dir"
    local session cwd target model launch pid path class
    IFS=$'\t' read -r session cwd target model launch < <(fleet_resolve "$name")
    {
      echo "hand=$name"
      echo "session=$session target=$target"
      echo "fleet_cwd=$cwd model=$model"
      echo "launch=${launch:-}"
    } >"$slot_dir/fleet.txt"

    if ! "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
      echo "class=down" >"$slot_dir/class.txt"
      continue
    fi

    path=$("$TMUX_BIN" display -p -t "$target" '#{pane_current_path}' 2>/dev/null || echo '?')
    pid=$(pane_pid "$target")
    class=$(classify "$target")
    {
      echo "class=$class"
      echo "pane_path=$path"
      echo "pane_pid=$pid pane_comm=$(pane_comm "$pid")"
      echo "kids:"
      for c in $("$PGREP_BIN" -P "$pid" 2>/dev/null || true); do
        echo "  $c $(pane_comm "$c") $($PS_BIN -p "$c" -o args= 2>/dev/null | cut -c1-120)"
        for g in $("$PGREP_BIN" -P "$c" 2>/dev/null || true); do
          echo "    grandchild $g $(pane_comm "$g")"
        done
      done
    } >"$slot_dir/topo.txt"

    "$TMUX_BIN" capture-pane -t "$target" -p -S -80 >"$slot_dir/pane-80.txt" 2>/dev/null || true
    echo "$class" >"$slot_dir/class.txt"
    if [[ -x "${VIVI_BIN:-}" ]]; then
      "$VIVI_BIN" board --project "$PROJECT" --for "$name" >"$slot_dir/board.txt" 2>&1 || true
    fi
  done

  # Index
  {
    echo "=== codex snapshot $stamp ==="
    echo "dir=$dir"
    for name in $names; do
      printf '%s class=%s\n' "$name" "$(cat "$dir/$name/class.txt" 2>/dev/null || echo '?')"
    done
  } | tee "$dir/INDEX.txt"
  echo "snapshot_dir=$dir"
}

# Bag-aware auto-reinit: only slots that doctor marks heal=yes.
# Never kills running turns. Bootstraps with first open handle when available.
cmd_heal() {
  local only="${1:-}"
  local names name
  local rc=0 r healed=0 skipped=0 failed=0 stuck=0
  local boot
  __BAG_STATUS_CACHE=""

  if [[ -n "$only" ]]; then
    names="$only"
  else
    names=$(codex_hand_names)
  fi

  log "======== HEAL start names=[$names] ========"
  echo "=== codex heal  $($DATE_BIN -u +%Y-%m-%dT%H:%M:%SZ) ==="

  for name in $names; do
    __heal_needed=0
    # doctor_one prints slot line; keep stdout for Mind ops.
    doctor_one "$name" 0
    if [[ ${__heal_needed:-0} -ne 1 ]]; then
      echo "  skip $name (no heal needed)"
      skipped=$((skipped + 1))
      echo
      continue
    fi

    # Re-check running under race: refuse unless FORCE
    local session cwd target model launch cls
    IFS=$'\t' read -r session cwd target model launch < <(fleet_resolve "$name")
    if "$TMUX_BIN" has-session -t "$session" 2>/dev/null; then
      cls=$(classify "$target")
      if [[ "$cls" == "running" && "${FORCE:-0}" != "1" ]]; then
        echo "  skip $name (now running)"
        skipped=$((skipped + 1))
        echo
        continue
      fi
    fi

    boot=$(default_boot "$name")
    echo "  HEAL $name → reinit"
    log "HEAL $name boot=${boot:0:120}"
    set +e
    cmd_reinit "$name" --boot "$boot"
    r=$?
    set -e
    if [[ $r -eq 0 ]]; then
      healed=$((healed + 1))
    elif [[ $r -eq 2 ]]; then
      stuck=$((stuck + 1))
      rc=2
      # auto snapshot on stuck for postmortem
      cmd_snapshot "$name" || true
    else
      failed=$((failed + 1))
      [[ $rc -eq 0 ]] && rc=1
      cmd_snapshot "$name" || true
    fi
    echo
  done

  log "HEAL done healed=$healed skipped=$skipped failed=$failed stuck=$stuck"
  echo "heal_summary healed=$healed skipped=$skipped failed=$failed stuck=$stuck exit=$rc"
  return $rc
}

# --- main ---
need_bins
: >>"$LOG"
cmd=${1:-}
shift || true
ROLE=""
_COMMAND_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project|-p) fleet_need_optarg "$1" "${2-}" || usage; PROJECT="$2"; shift 2 ;;
    --fleet|-f) fleet_need_optarg "$1" "${2-}" || usage; FLEET_ID="$2"; shift 2 ;;
    --fleet-file) fleet_need_optarg "$1" "${2-}" || usage; FLEET_FILE="$2"; shift 2 ;;
    --runtime-target) fleet_need_optarg "$1" "${2-}" || usage; RUNTIME_TARGET="$2"; shift 2 ;;
    --role) fleet_need_optarg "$1" "${2-}" || usage; ROLE="$2"; shift 2 ;;
    *) _COMMAND_ARGS+=("$1"); shift ;;
  esac
done
FLEET_FILE="${FLEET_FILE:-$PROJECT/.vivi/fleet.json}"
case "$cmd" in
  status) [[ -n "$ROLE" ]] || usage; cmd_status "$ROLE" ;;
  classify)
    [[ -n "$ROLE" ]] || usage
    IFS=$'\t' read -r session cwd target model launch < <(fleet_resolve "$ROLE")
    echo "$(classify "$target")"
    ;;
  doctor|probe|debug)
    cmd_doctor "${ROLE:-}"
    ;;
  snapshot|dump)
    cmd_snapshot "${ROLE:-}"
    ;;
  heal)
    cmd_heal "${ROLE:-}"
    ;;
  reinit) [[ -n "$ROLE" ]] || usage; cmd_reinit "$ROLE" "${_COMMAND_ARGS[@]}" ;;
  reinit-all) cmd_reinit_all "${_COMMAND_ARGS[@]}" ;;
  topo)
    [[ -n "$ROLE" ]] || usage
    IFS=$'\t' read -r session cwd target model launch < <(fleet_resolve "$ROLE")
    topo "$target"
    ;;
  -h|--help|help|"") usage ;;
  *) die "unknown command: $cmd" ;;
esac
