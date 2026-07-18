#!/usr/bin/env bash
# Pointer-only Hand/Head wake via fleet.json tmux_target / vivi_pty.
#
# Usage:
#   fleet-doorbell.sh --project <root> --role hand-1 [--handle HEX] [--note '…'] [--force]
#   fleet-doorbell.sh --project <root> --role hand-1 --runtime-target mgs:hand-1.1
#   fleet-doorbell.sh --project <root> --role hand-1 --handle HEX --mode new
#   fleet-doorbell.sh --project <root> --role hand-1 --handle HEX --no-prepare
#
# assignment_mode (per role in fleet.json; overridable with --mode):
#   new      — fresh agent session (/new or recreate) before pointer when handle is new
#   compact  — /compact then pointer when handle is new
#   continue — pointer only (default when unset)
#   restart  — fleet-runtime restart then pointer when handle is new
# Same-handle rewake does not re-apply mode (unless --force-prepare).
#
# /new and /compact are transition-aware: a new-session wake records success
# only after the command demonstrably changes the pane (no stale-idle race) and
# the pointer is positively acknowledged as leaving idle. See
# wait_command_transition and verify_pointer_submission_started.
#
# Requires: bash 3.2+ (not sh/zsh-as-script), python3 >= 3.9
# Backing runtime: tmux (default) or vivi-pty for roles with runtime.kind=vivi_pty.
# Portable: macOS + Linux. Override with TMUX_BIN / VIVI_PTY_BIN / PYTHON_BIN /
# FLEET_DOORBELL_SUBMIT_DELAY_SEC / FLEET_DOORBELL_PREPARE_TIMEOUT_SEC /
# FLEET_DOORBELL_TRANSITION_TIMEOUT_SEC / FLEET_DOORBELL_SUBMIT_ACK_TIMEOUT_SEC.
#
# Rate limit (min_seconds_between_wakes): only if this Hand has prior wake
# count >= 1 in baseline last_hand_wake.by_hand.<name>. First wake never limited.
#
# Exit: 0 sent · 1 refused (running / unready shell / rate-limit / missing / prepare fail) · 2 usage/config error
#
# Safety: tmux classify is FAIL-CLOSED. Only positive agent chrome → send-keys+Enter.
# Bare zsh/bash (or unknown screens) → state=unready → refuse (never type HAND WAKE into a shell).
set -euo pipefail

_FLEET_SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=lib/env.sh
. "$_FLEET_SCRIPT_DIR/lib/env.sh"
fleet_bootstrap_env

PROJECT=""
ROLE=""
FLEET_ID=""
FLEET_FILE=""
HANDLE=""
NOTE=""
FORCE=0
FORCE_PREPARE=0
NO_PREPARE=0
MODE_OVERRIDE=""
TARGET=""
MESSAGE=""
SUBMIT_DELAY="${FLEET_DOORBELL_SUBMIT_DELAY_SEC:-}"
PREPARE_TIMEOUT="${FLEET_DOORBELL_PREPARE_TIMEOUT_SEC:-45}"
# Bounded window for a /new or /compact command to change the pane (transition
# away from the pre-command idle screen). Polls ~10Hz; never a blind sleep.
TRANSITION_TIMEOUT="${FLEET_DOORBELL_TRANSITION_TIMEOUT_SEC:-8}"
# Bounded window for a submitted pointer to be acknowledged (runtime leaves
# idle/completed and enters running/submitting/approval).
SUBMIT_ACK_TIMEOUT="${FLEET_DOORBELL_SUBMIT_ACK_TIMEOUT_SEC:-5}"
# Bounded post-recreate readiness stabilization window. A freshly recreated
# runtime (Pi assignment_mode=new) can paint idle agent chrome before its input
# handling is wired: the pane classifies as waiting_for_input yet a pasted
# pointer is dropped / Enter ignored until readiness matures (a paste->Enter
# delay cannot recover a paste delivered before readiness). wait_stable_input
# dwells this window (polling ~10Hz, aborting on regression) before send_line,
# so delivery starts after readiness. Runs only after a recreate; overridable.
STABLE_WINDOW="${FLEET_DOORBELL_STABLE_WINDOW_SEC:-1.0}"

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
  fleet_usage_from_header "$0" 2 18
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
    --role)
      fleet_need_optarg "$1" "${2-}" || usage
      ROLE="$2"
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
    --mode)
      fleet_need_optarg "$1" "${2-}" || usage
      MODE_OVERRIDE="$2"
      shift 2
      ;;
    --force) FORCE=1; shift ;;
    --force-prepare) FORCE_PREPARE=1; shift ;;
    --no-prepare) NO_PREPARE=1; shift ;;
    --runtime-target)
      fleet_need_optarg "$1" "${2-}" || usage
      TARGET="$2"
      shift 2
      ;;
    --message)
      fleet_need_optarg "$1" "${2-}" || usage
      MESSAGE="$2"
      shift 2
      ;;
    --prepare-timeout)
      fleet_need_optarg "$1" "${2-}" || usage
      PREPARE_TIMEOUT="$2"
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
      echo "unexpected positional argument: $1 (use --role)" >&2
      usage
      ;;
  esac
done

[[ -n "$PROJECT" ]] || usage
if ! PROJECT="$(fleet_abs_project "$PROJECT")"; then
  echo "ERROR: project is not a directory: $PROJECT" >&2
  exit 2
fi
FLEET_FILE="${FLEET_FILE:-$PROJECT/.vivi/fleet.json}"
BASELINE="${BASELINE:-$PROJECT/.vivi/mind-baseline.json}"
[[ -f "$FLEET_FILE" ]] || { echo "missing fleet.json: $FLEET_FILE" >&2; exit 2; }

# Resolve logical role through the shared backend-neutral resolver. Wake history
# is a separate baseline concern and is intentionally not part of target
# resolution.
resolve() {
  local resolver=("$PYTHON_BIN" "$_FLEET_SCRIPT_DIR/fleet-resolve.py"
    --project "$PROJECT" --fleet-file "$FLEET_FILE" --role "$ROLE" --shell)
  [[ -n "$FLEET_ID" ]] && resolver+=(--fleet "$FLEET_ID")
  [[ -n "$TARGET" ]] && resolver+=(--runtime-target "$TARGET")
  "${resolver[@]}"
  "$PYTHON_BIN" - "$BASELINE" "$ROLE" <<'PY'
import json, shlex, sys
from pathlib import Path

path, role = sys.argv[1:3]
baseline = {}
if Path(path).is_file():
    try:
        baseline = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        pass
by = ((baseline.get("last_hand_wake") or {}).get("by_hand") or {})
entry = by.get(role) if isinstance(by, dict) else None
last_at = entry.get("at", "") if isinstance(entry, dict) else ""
wake_count = int(entry.get("count", 0) or 0) if isinstance(entry, dict) else 0
last_handle = entry.get("handle") if isinstance(entry, dict) else None
if not last_at:
    legacy = baseline.get("last_hand_wake") if isinstance(baseline.get("last_hand_wake"), dict) else {}
    if legacy.get("target") == role:
        last_at = legacy.get("at") or baseline.get("last_hand_wake_at") or ""
        wake_count = 1 if last_at else 0
        last_handle = legacy.get("handle")
print("RESOLVED_LAST_AT=" + shlex.quote(str(last_at or "")))
print("RESOLVED_WAKE_COUNT=" + shlex.quote(str(wake_count)))
print("RESOLVED_LAST_HANDLE=" + shlex.quote("" if last_handle is None else str(last_handle)))
PY
}

# Exact tmux session name (avoid prefix match: swarm vs swarm-cli).
# Bare names are prefixes on tmux 3.x — "swarm" matches "swarm-cli".
tmux_session_exact() {
  local target=$1
  local session=${target%%:*}
  session=${session#=}
  printf '%s\n' "=${session}"
}

# Exact full target (session:window.pane) for capture/send-keys.
tmux_target_exact() {
  local target=$1
  local session rest
  if [[ "$target" == =* ]]; then
    printf '%s\n' "$target"
    return 0
  fi
  if [[ "$target" == *:* ]]; then
    session=${target%%:*}
    rest=${target#*:}
    printf '%s\n' "=${session}:${rest}"
  else
    printf '%s\n' "=${target}"
  fi
}

# Classify pane quickly (subset of fleet-sensors heuristics; BSD+GNU grep -Eiq).
#
# FAIL-CLOSED: only positive agent chrome → waiting_for_input / completed.
# Bare shells and unrecognized screens → unready (never default to "ready").
# Doorbell must not send-keys+Enter into zsh/bash (treats HAND as a command).
classify_tmux_text() {
  local t=$1
  # Order matters: first match wins.
  if printf '%s\n' "$t" | grep -Eiq \
    'Working \(|esc to interrupt|Waiting for response|Responding|Working\.\.\.|Thinking…|Thinking\.\.\.|⬝|(🌑|🌒|🌓|🌔|🌕|🌖|🌗|🌘)[[:space:]]*·[[:space:]]*Tip:'; then
    echo running
    return 0
  fi
  if printf '%s\n' "$t" | grep -Eiq \
    'Yes, continue|Do you trust|trust this workspace|Always allow|Allow always|Allow once|until OpenCode is restarted|No, quit|Press enter to continue|Approve once|Approve for this session|Reject with feedback|Write this file\?|↵ confirm'; then
    echo approval_required
    return 0
  fi
  if printf '%s\n' "$t" | grep -Eiq \
    'over capacity|rate limit|usage limit'; then
    echo failed
    return 0
  fi
  # Kimi ready chrome must be current at the bottom, not stale scrollback.
  local bottom
  bottom="$(printf '%s\n' "$t" | awk 'NF { lines[++n] = $0 } END { start = n > 6 ? n - 5 : 1; for (i = start; i <= n; i++) print lines[i] }')"
  if printf '%s\n' "$bottom" | awk 'NF { line = $0 } END { print line }' | grep -Eiq 'context:[[:space:]]*[0-9]+%' && \
     printf '%s\n' "$bottom" | grep -Eq '│[[:space:]]*>[[:space:]]*'; then
    echo waiting_for_input
    return 0
  fi
  # Positive agent-idle markers only (do not treat shell %/$ as ready).
  # Pi (pi-hand): footer like "0.0%/1.0M (auto) … (zai) glm-5.2 • low" or "pi v0.80".
  if printf '%s\n' "$t" | grep -Eiq \
    '›|codex ›|\$0\.|openai-codex|Ask anything|OpenCode Zen|Build ·|ctrl\+p commands|always-approve|Shift\+Tab|Idle until|Board empty|bag empty|Turn completed|actionable: 0|╰─|pi-lite|Grok  |Grok$|pi v0\.|\(zai\)|glm-5\.2|escape interrupt|%/1\.0M \(auto\)|mgs-hand-'; then
    if printf '%s\n' "$t" | grep -Eiq \
      'bag empty|standing by|turn end|Turn completed|ready-to-merge|Idle until|Board empty|actionable: 0'; then
      echo completed
      return 0
    fi
    echo waiting_for_input
    return 0
  fi
  # Explicit shell / non-agent errors — refuse doorbell (keystroke injection risk).
  if printf '%s\n' "$t" | grep -Eiq 'command not found:|^zsh:|^bash:|^fish:'; then
    echo unready
    return 0
  fi
  # Last non-empty line looks like a classic shell prompt (%, $, #) without agent chrome.
  local last
  last="$(printf '%s\n' "$t" | awk 'NF { line = $0 } END { print line }')"
  if printf '%s\n' "$last" | grep -Eq '^[[:space:]]*[%$#]([[:space:]]|$)'; then
    echo unready
    return 0
  fi
  # Unrecognized screen — fail closed (historical bug: defaulted waiting_for_input).
  echo unready
  return 0
}

classify() {
  local target=$1
  local session_exact target_exact
  session_exact="$(tmux_session_exact "$target")"
  target_exact="$(tmux_target_exact "$target")"
  local t
  if ! "$TMUX_BIN" has-session -t "$session_exact" 2>/dev/null; then
    echo stopped
    return 0
  fi
  t="$("$TMUX_BIN" capture-pane -t "$target_exact" -p -S -20 2>/dev/null || true)"
  classify_tmux_text "$t"
}

# Read vivi-pty harness state; when driver reports unknown/unready, fall back to
# the same positive-chrome heuristics as classify_tmux_text (terminal contents).
# Fail-closed still applies for bare shells — only agent-idle markers pass.
classify_vivi_pty() {
  local session_id=$1
  local socket=$2
  local diag
  if ! diag=$("$VIVI_PTY_BIN" session diagnostic "$session_id" --socket "$socket" 2>/dev/null); then
    echo stopped
    return 0
  fi
  printf '%s\n' "$diag" | "$PYTHON_BIN" -c '
import json, re, sys

def classify_text(t: str) -> str:
    lines = [ln for ln in t.splitlines() if ln.strip()]
    bottom = "\n".join(lines[-6:]) if lines else ""
    if re.search(
        r"Working \(|esc to interrupt|Waiting for response|Responding|Working\.\.\.|Thinking…|Thinking\.\.\.|⬝|[🌑🌒🌓🌔🌕🌖🌗🌘]\s*·\s*Tip:",
        t,
        re.I,
    ):
        return "running"
    if re.search(
        r"Yes, continue|Do you trust|trust this workspace|Always allow|Allow always|Allow once|until OpenCode is restarted|No, quit|Press enter to continue|Approve once|Approve for this session|Reject with feedback|Write this file\?|↵ confirm",
        t,
        re.I,
    ):
        return "approval_required"
    if re.search(r"over capacity|rate limit|usage limit", t, re.I):
        return "failed"
    if lines and re.search(r"context:\s*\d+%", lines[-1]) and re.search(r"│\s*>\s*", bottom):
        return "waiting_for_input"
    if re.search(
        r"›|codex ›|\$0\.|openai-codex|Ask anything|OpenCode Zen|Build ·|ctrl\+p commands|always-approve|Shift\+Tab|Idle until|Board empty|bag empty|Turn completed|actionable: 0|╰─|pi-lite|Grok  |Grok$|◇ candidate|pi v0\.|\(zai\)|glm-5\.2|escape interrupt|%/1\.0M \(auto\)|mgs-hand-",
        t,
        re.I,
    ):
        if re.search(
            r"bag empty|standing by|turn end|Turn completed|ready-to-merge|Idle until|Board empty|actionable: 0",
            t,
            re.I,
        ):
            return "completed"
        return "waiting_for_input"
    if re.search(r"command not found:|^zsh:|^bash:|^fish:", t, re.I | re.M):
        return "unready"
    last = lines[-1] if lines else ""
    if re.match(r"^[\s]*[%$#]([\s]|$)", last):
        return "unready"
    return "unready"

try:
    data = json.load(sys.stdin)
    process = data.get("process_state") or data.get("session", {}).get("state")
    if process in ("exited", "stopped"):
        print("stopped")
        raise SystemExit(0)
    harness = data.get("harness_state") or "unknown"
    # Canonical driver states when present and decisive.
    if harness in ("running", "waiting_for_input", "completed", "approval_required", "failed", "stopped"):
        print(harness)
        raise SystemExit(0)
    # unknown/unready/empty: classify terminal contents (fail-closed).
    term = (data.get("terminal") or {}).get("contents") or ""
    print(classify_text(term))
except SystemExit:
    raise
except Exception:
    print("unknown")
'
}

classify_runtime() {
  if [[ "$WAKE_MODE" == "vivi_pty" ]]; then
    classify_vivi_pty "$RESOLVED_TARGET" "$SOCKET"
  else
    classify "$RESOLVED_TARGET"
  fi
}

submit_delay_default() {
  if [[ -n "$SUBMIT_DELAY" ]]; then
    printf '%s\n' "$SUBMIT_DELAY"
    return 0
  fi
  if [[ "$WAKE_MODE" == "vivi_pty" ]]; then
    case "$AGENT" in
      kimi) printf '0.8\n' ;;
      *) printf '0.05\n' ;;
    esac
    return 0
  fi
  case "$AGENT" in
    codex) printf '0.8\n' ;;
    kimi) printf '3.0\n' ;;
    grok|pi|opencode) printf '0.05\n' ;;
    *) printf '0.05\n' ;;
  esac
}

# Send one line + Enter to the role runtime (tmux or vivi_pty).
send_line() {
  local text=$1
  local delay
  delay="$(submit_delay_default)"
  text="$(printf '%s' "$text" | tr '\n\r' '  ')"
  if [[ "$WAKE_MODE" == "vivi_pty" ]]; then
    if [[ "$AGENT" == "kimi" ]]; then
      # Kimi needs paste settling before Enter; an atomic write --enter can
      # leave a complete wake pointer sitting unsent in the composer.
      "$VIVI_PTY_BIN" terminal write "$RESOLVED_TARGET" "$text" --socket "$SOCKET"
      sleep "$delay"
      "$VIVI_PTY_BIN" terminal key "$RESOLVED_TARGET" Enter --socket "$SOCKET"
    else
      "$VIVI_PTY_BIN" terminal write "$RESOLVED_TARGET" "$text" --enter --socket "$SOCKET"
      sleep "$delay"
    fi
  else
    local target_exact
    target_exact="$(tmux_target_exact "$RESOLVED_TARGET")"
    "$TMUX_BIN" send-keys -t "$target_exact" -l -- "$text"
    sleep "$delay"
    "$TMUX_BIN" send-keys -t "$target_exact" Enter
  fi
}

verify_pointer_submission_started() {
  # Acknowledgement is required only when an actual preparation (new/compact/
  # restart) ran and succeeded — the sole case where the doorbell invariant
  # forbids recording baseline success from keystroke delivery alone.
  # Eligibility (APPLY_PREPARE) is intentionally not enough: assignment_mode
  # =continue with a new handle skips preparation, so it must preserve the
  # historical pointer-only behavior (only Kimi under vivi_pty required ack).
  if [[ "$DID_PREPARE" -ne 1 ]]; then
    [[ "$WAKE_MODE" == "vivi_pty" && "$AGENT" == "kimi" ]] || return 0
  fi
  local i=0
  local state
  local budget=$((SUBMIT_ACK_TIMEOUT * 10))
  while [[ "$i" -lt "$budget" ]]; do
    state="$(classify_runtime)"
    case "$state" in
      running|submitting|approval_required) return 0 ;;
      stopped|failed|unready|unknown) break ;;
    esac
    sleep 0.1
    i=$((i + 1))
  done
  echo "refused: pointer submission was not acknowledged (state=$state); wake not recorded" >&2
  return 1
}

# True when it is safe to type a pointer (or /new|/compact) into the pane.
agent_accepts_input() {
  case "$1" in
    waiting_for_input|completed) return 0 ;;
    *) return 1 ;;
  esac
}

# Wait until agent looks idle enough for input (or timeout).
# Fail closed: unknown/unready never count as ready (shells must not pass).
wait_ready() {
  local timeout=${1:-$PREPARE_TIMEOUT}
  local i=0
  local state
  # bash 3.2: no ((i < timeout)) with empty; use string compare carefully
  while [[ "$i" -lt "$timeout" ]]; do
    state="$(classify_runtime)"
    case "$state" in
      waiting_for_input|completed)
        CLASS="$state"
        return 0
        ;;
      stopped|unready|unknown|failed|approval_required)
        CLASS="$state"
        # unready/unknown: keep waiting briefly in case chrome is late after start
        if [[ "$state" == "stopped" || "$state" == "failed" || "$state" == "approval_required" ]]; then
          return 1
        fi
        ;;
      running|starting|submitting)
        ;;
    esac
    sleep 1
    i=$((i + 1))
  done
  CLASS="$(classify_runtime)"
  return 1
}

# Bounded post-recreate readiness stabilization. A freshly recreated runtime
# (Pi assignment_mode=new) can paint idle agent chrome before its input handling
# is wired: the pane classifies as waiting_for_input yet a pasted pointer is
# dropped / Enter ignored until readiness matures. wait_ready latches on the
# first idle sample; this dwell confirms readiness by surviving a bounded window
# in an input-accepting state, aborting (refuse) if the runtime regresses.
# Readiness is reached by surviving the window, not by a lone pane sample or a
# paste->Enter gap. Runs only after a recreate (DID_RECREATE), before send_line.
wait_stable_input() {
  local window=${1:-$STABLE_WINDOW}
  local i=0
  # Poll budget at ~10Hz (0.1s cadence). bash arithmetic is integer-only, so a
  # fractional STABLE_WINDOW (e.g. 0.8s) is converted to a poll count via awk
  # (already a doorbell dependency). Floor to whole polls.
  local budget
  budget="$(awk -v w="$window" 'BEGIN { printf "%d", int((w + 0) * 10) }')" 2>/dev/null || budget=0
  local state
  while [[ "$i" -lt "$budget" ]]; do
    state="$(classify_runtime)"
    case "$state" in
      waiting_for_input|completed) ;;
      *) return 1 ;;
    esac
    sleep 0.1
    i=$((i + 1))
  done
  return 0
}

runtime_lifecycle() {
  # start | restart for this role via fleet-runtime.py. FLEET_RUNTIME_PY is a
  # focused test seam (defaults to the canonical script); production unset.
  local action=$1
  local runtime_py="${FLEET_RUNTIME_PY:-$_FLEET_SCRIPT_DIR/fleet-runtime.py}"
  local args=("$PYTHON_BIN" "$runtime_py"
    --project "$PROJECT" --role "$ROLE" "$action" --force)
  [[ -n "$FLEET_ID" ]] && args+=(--fleet "$FLEET_ID")
  [[ -n "$FLEET_FILE" ]] && args+=(--fleet-file "$FLEET_FILE")
  "${args[@]}"
}

# Compact, deterministic signature of the current runtime screen (last few
# non-empty lines). Used to detect that a /new or /compact command actually
# changed the pane, rather than a stale pre-command idle screen being mistaken
# for a successful transition. tmux: capture-pane; vivi_pty: diagnostic contents.
runtime_signature() {
  local raw=""
  if [[ "$WAKE_MODE" == "vivi_pty" ]]; then
    raw="$("$VIVI_PTY_BIN" session diagnostic "$RESOLVED_TARGET" --socket "$SOCKET" 2>/dev/null \
      | "$PYTHON_BIN" -c 'import json,sys
try:
    d=json.load(sys.stdin)
    print(((d.get("terminal") or {}).get("contents") or ""))
except Exception:
    print("")' 2>/dev/null || true)"
  else
    local target_exact
    target_exact="$(tmux_target_exact "$RESOLVED_TARGET")"
    raw="$("$TMUX_BIN" capture-pane -t "$target_exact" -p -S -20 2>/dev/null || true)"
  fi
  printf '%s\n' "$raw" | awk 'NF { lines[++n]=$0 } END { start = n>8 ? n-7 : 1; for (i=start;i<=n;i++) printf "%s\n", lines[i] }' | tr -d '\r'
}

# Poll until the runtime screen differs from `before` (the command took effect)
# or `timeout` seconds elapse. Proves a /new or /compact transitioned away from
# the pre-command idle screen instead of wait_ready latching onto stale chrome.
# Bounded (polls ~10Hz); never a blind sleep. Returns 0 on transition, 1 timeout.
# A capture failure (empty signature) never counts as a transition (fail-closed).
wait_command_transition() {
  local before=$1
  local timeout=${2:-$TRANSITION_TIMEOUT}
  local i=0
  local now
  while [[ "$i" -lt $((timeout * 10)) ]]; do
    now="$(runtime_signature)"
    if [[ -n "$now" && "$now" != "$before" ]]; then
      return 0
    fi
    sleep 0.1
    i=$((i + 1))
  done
  return 1
}

prepare_assignment() {
  local mode=$1
  case "$mode" in
    continue|"")
      return 0
      ;;
    compact)
      if [[ "$(classify_runtime)" == "stopped" ]]; then
        if ! runtime_lifecycle start >/dev/null; then
          echo "refused: assignment_mode=compact could not start runtime $RESOLVED_TARGET" >&2
          return 1
        fi
        if ! wait_ready "$PREPARE_TIMEOUT"; then
          echo "refused: assignment_mode=compact runtime not ready after start ($CLASS)" >&2
          return 1
        fi
      fi
      CLASS="$(classify_runtime)"
      if [[ "$CLASS" =~ ^(starting|submitting|running|approval_required)$ ]]; then
        echo "refused: assignment_mode=compact needs idle runtime, state=$CLASS" >&2
        return 1
      fi
      if ! agent_accepts_input "$CLASS"; then
        echo "refused: assignment_mode=compact pane is not an agent prompt (state=$CLASS) — will not type into shell" >&2
        return 1
      fi
      echo "prepare: compact on $RESOLVED_TARGET" >&2
      local pre_compact_sig
      pre_compact_sig="$(runtime_signature)"
      send_line "/compact"
      if ! wait_command_transition "$pre_compact_sig" "$TRANSITION_TIMEOUT"; then
        echo "refused: assignment_mode=compact did not transition after /compact (stale idle) ($RESOLVED_TARGET)" >&2
        return 1
      fi
      if ! wait_ready "$PREPARE_TIMEOUT"; then
        echo "refused: assignment_mode=compact did not return to idle ($CLASS)" >&2
        return 1
      fi
      return 0
      ;;
    new)
      if [[ "$(classify_runtime)" == "stopped" ]]; then
        if ! runtime_lifecycle start >/dev/null; then
          echo "refused: assignment_mode=new could not start runtime $RESOLVED_TARGET" >&2
          return 1
        fi
        if ! wait_ready "$PREPARE_TIMEOUT"; then
          echo "refused: assignment_mode=new runtime not ready after start ($CLASS)" >&2
          return 1
        fi
        # Fresh process already has empty context — skip /new.
        return 0
      fi
      CLASS="$(classify_runtime)"
      if [[ "$CLASS" =~ ^(starting|submitting|running|approval_required)$ ]]; then
        echo "refused: assignment_mode=new needs idle runtime, state=$CLASS" >&2
        return 1
      fi
      if ! agent_accepts_input "$CLASS"; then
        echo "refused: assignment_mode=new pane is not an agent prompt (state=$CLASS) — will not type into shell" >&2
        return 1
      fi
      # Pi: in-process /new does not yield a usable composer (the pointer is
      # erased and the pane appears idle but rejects later input). Recreate
      # the role runtime instead — the documented "new or recreate" contract —
      # then pointer-only delivery. Shared tmux sessions are preserved by the
      # role-window restart boundary in fleet-runtime.py. No /new is sent.
      if [[ "$AGENT" == "pi" ]]; then
        echo "prepare: recreate pi runtime for new session on $RESOLVED_TARGET" >&2
        if ! runtime_lifecycle restart >/dev/null; then
          echo "refused: assignment_mode=new pi runtime recreate failed for $ROLE" >&2
          return 1
        fi
        find_backing_tools
        if ! wait_ready "$PREPARE_TIMEOUT"; then
          echo "refused: assignment_mode=new pi runtime not ready after recreate ($CLASS)" >&2
          return 1
        fi
        DID_RECREATE=1
        return 0
      fi
      echo "prepare: new session on $RESOLVED_TARGET" >&2
      local pre_new_sig
      pre_new_sig="$(runtime_signature)"
      send_line "/new"
      if ! wait_command_transition "$pre_new_sig" "$TRANSITION_TIMEOUT"; then
        echo "refused: assignment_mode=new did not transition after /new (stale idle) ($RESOLVED_TARGET)" >&2
        return 1
      fi
      if ! wait_ready "$PREPARE_TIMEOUT"; then
        echo "refused: assignment_mode=new did not return to idle after /new ($CLASS)" >&2
        return 1
      fi
      return 0
      ;;
    restart)
      echo "prepare: restart runtime $RESOLVED_TARGET" >&2
      if ! runtime_lifecycle restart >/dev/null; then
        echo "refused: assignment_mode=restart failed for $ROLE" >&2
        return 1
      fi
      # Re-resolve tools in case backend came up late
      find_backing_tools
      if ! wait_ready "$PREPARE_TIMEOUT"; then
        echo "refused: assignment_mode=restart runtime not ready ($CLASS)" >&2
        return 1
      fi
      return 0
      ;;
    *)
      echo "refused: unknown assignment_mode $mode" >&2
      return 1
      ;;
  esac
}

RESOLVED_TARGET=""
SESSION=""
AGENT="unknown"
MIN_GAP=0
MAIL=""
LAST_AT=""
WAKE_COUNT=0
LAST_HANDLE=""
ASSIGNMENT_MODE="continue"
FLEET_ID_RESOLVED=""

if [[ -n "$MESSAGE" && -n "$TARGET" && -z "$ROLE" ]]; then
  RESOLVED_TARGET="$TARGET"
  WAKE_MODE="tmux_send_keys"
  AGENT="unknown"
  MAIL=""
  MIN_GAP=0
  LAST_AT=""
  WAKE_COUNT=0
  LAST_HANDLE=""
  ASSIGNMENT_MODE="continue"
  SOCKET=""
  SESSION="${TARGET%%:*}"
elif [[ -n "$ROLE" ]]; then
  eval "$(resolve)"
  RESOLVED_TARGET="${RESOLVED_TARGET:-}"
  SESSION="${RESOLVED_SESSION:-}"
  AGENT="${RESOLVED_AGENT:-unknown}"
  MIN_GAP="${RESOLVED_MIN_SECONDS_BETWEEN_WAKES:-180}"
  MAIL="${RESOLVED_MAIL_IDENTITY:-$ROLE}"
  WAKE_MODE="${RESOLVED_KIND:-tmux}"
  [[ "$WAKE_MODE" == "vivi_pty" ]] || WAKE_MODE="tmux_send_keys"
  SOCKET="${RESOLVED_SOCKET:-}"
  ASSIGNMENT_MODE="${RESOLVED_ASSIGNMENT_MODE:-continue}"
  LAST_HANDLE="${RESOLVED_LAST_HANDLE:-}"
  FLEET_ID_RESOLVED="${RESOLVED_FLEET_ID:-}"
  [[ -n "$FLEET_ID" ]] || FLEET_ID="$FLEET_ID_RESOLVED"
else
  usage
fi

if [[ -n "$MODE_OVERRIDE" ]]; then
  ASSIGNMENT_MODE="$(printf '%s' "$MODE_OVERRIDE" | tr '[:upper:]' '[:lower:]')"
fi
case "$ASSIGNMENT_MODE" in
  new|compact|continue|restart) ;;
  *)
    echo "ERROR: assignment_mode must be new|compact|continue|restart, got $ASSIGNMENT_MODE" >&2
    exit 2
    ;;
esac

WAKE_MODE="${WAKE_MODE:-tmux_send_keys}"
find_backing_tools

# Classify pane/session quickly before sending.
CLASS="$(classify_runtime)"

# Decide whether to apply assignment_mode prepare (new work item only).
APPLY_PREPARE=0
if [[ "$NO_PREPARE" -eq 1 ]]; then
  APPLY_PREPARE=0
elif [[ "$FORCE_PREPARE" -eq 1 ]]; then
  APPLY_PREPARE=1
elif [[ -n "$HANDLE" && "$HANDLE" != "$LAST_HANDLE" ]]; then
  # New handle (or first recorded handle) → prepare per mode.
  APPLY_PREPARE=1
elif [[ -z "$HANDLE" && "$ASSIGNMENT_MODE" == "restart" && "$CLASS" == "stopped" ]]; then
  APPLY_PREPARE=1
elif [[ -z "$HANDLE" && "$ASSIGNMENT_MODE" == "new" && "$CLASS" == "stopped" ]]; then
  APPLY_PREPARE=1
else
  # Same handle rewake, or pointer-only bag scan: no re-prepare.
  APPLY_PREPARE=0
fi

# DID_PREPARE tracks whether a new/compact/restart preparation actually ran
# and succeeded, separate from APPLY_PREPARE eligibility. It gates forced
# pointer acknowledgement below (continue-mode new handle stays pointer-only).
DID_PREPARE=0
DID_RECREATE=0
if [[ "$APPLY_PREPARE" -eq 1 && "$ASSIGNMENT_MODE" != "continue" ]]; then
  if ! prepare_assignment "$ASSIGNMENT_MODE"; then
    exit 1
  fi
  DID_PREPARE=1
  CLASS="$(classify_runtime)"
elif [[ "$CLASS" == "stopped" ]]; then
  # continue (or skipped prepare): still need a live runtime for pointer wake
  if [[ -n "$ROLE" ]]; then
    echo "prepare: start stopped runtime $RESOLVED_TARGET" >&2
    if ! runtime_lifecycle start >/dev/null; then
      echo "refused: no runtime session for $RESOLVED_TARGET" >&2
      exit 1
    fi
    if ! wait_ready "$PREPARE_TIMEOUT"; then
      echo "refused: runtime not ready after start ($CLASS)" >&2
      exit 1
    fi
    CLASS="$(classify_runtime)"
  else
    echo "refused: no runtime session for $RESOLVED_TARGET" >&2
    exit 1
  fi
fi

# Fail closed: only agent idle/completed may receive keystrokes (+ Enter).
# Bare shell / unmatched pane classifies as unready — never send HAND WAKE into zsh.
if [[ "$CLASS" == "stopped" ]]; then
  echo "refused: no runtime session for $RESOLVED_TARGET" >&2
  exit 1
fi
if [[ "$FORCE" -ne 1 ]]; then
  if [[ "$CLASS" =~ ^(starting|submitting|running|approval_required|failed)$ ]]; then
    echo "refused: runtime $RESOLVED_TARGET state=$CLASS" >&2
    exit 1
  fi
  if ! agent_accepts_input "$CLASS"; then
    echo "refused: runtime $RESOLVED_TARGET state=$CLASS (not an agent input prompt; refuse shell/keystroke injection)" >&2
    exit 1
  fi
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
      echo "refused: rate limit ${DELTA}s < ${MIN_GAP}s since last wake of $ROLE (count=${WAKE_COUNT})" >&2
      exit 1
    fi
  fi
fi

# Build pointer message
if [[ -z "$MESSAGE" ]]; then
  PROJECT_Q="$PROJECT"
  MAIL_Q="${MAIL:-$ROLE}"
  if [[ -n "$HANDLE" ]]; then
    MESSAGE="HAND WAKE ${ROLE}. Bag: show ${HANDLE}. vivi --project ${PROJECT_Q} --for ${MAIL_Q}. ${NOTE} Continue."
  else
    MESSAGE="HAND WAKE ${ROLE}. Bag: show next open. vivi --project ${PROJECT_Q} --for ${MAIL_Q}. ${NOTE} Continue."
  fi
fi

# strip newlines / CRs from pointer (portable tr)
MESSAGE="$(printf '%s' "$MESSAGE" | tr '\n\r' '  ')"

# Pre-send post-recreate readiness stabilization: a freshly recreated runtime
# can look idle before it can accept a pasted pointer (idle chrome paints
# before input handling is wired). Dwell a bounded window (confirmed stable)
# before any keystrokes so the paste lands on a ready composer. Delivery starts
# after readiness; this is not a paste->Enter delay.
if [[ "$DID_RECREATE" -eq 1 ]]; then
  if ! wait_stable_input "$STABLE_WINDOW"; then
    echo "refused: post-recreate runtime did not stabilize (regressed during readiness window) $RESOLVED_TARGET" >&2
    exit 1
  fi
  CLASS="$(classify_runtime)"
fi

send_line "$MESSAGE"
verify_pointer_submission_started || exit 1

# record last wake in baseline (atomic write)
"$PYTHON_BIN" - "$BASELINE" "$PROJECT" "$ROLE" "$HANDLE" "$RESOLVED_TARGET" "$WAKE_MODE" "$SOCKET" "$ASSIGNMENT_MODE" <<'PY'
import json, os, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone

path, project, name, handle, target, wake_mode, socket, assignment_mode = sys.argv[1:9]
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
entry = {
    "at": now,
    "count": count,
    "handle": handle or None,
    "runtime": runtime,
    "assignment_mode": assignment_mode or None,
}
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
    "assignment_mode": assignment_mode or None,
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
sys.stdout.write(
    "sent\t%s\t%s\t%s\t%s\tmode=%s\n"
    % (target, name or "", handle or "", now, assignment_mode or "")
)
PY

exit 0
