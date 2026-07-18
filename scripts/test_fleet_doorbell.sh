#!/usr/bin/env bash
# Focused tests for scripts/fleet-doorbell.sh — Pi /new pointer-loss race.
#
# Covers the transition-aware preparation + pointer acknowledgement fix and the
# Pi new-session recreate path:
#   1. stale-idle immediate classifier race (codex /new)  => refuse, no record
#   2. delayed /new transition (codex)                    => success, recorded
#   3. successful fresh readiness (codex /new)            => success, recorded
#   4. pointer never acknowledged (codex /new)            => refuse, no record
#   5. continue + new handle, no --no-prepare (pi)        => success, no ack (P1)
#   6. pointer never acknowledged (pi compact)            => refuse, no record
#   7. pi new recreates runtime, no /new                  => success, recorded
#   8. pi new recreate failure                            => refuse, no record
#   9. pi pointer delivered before recreate readiness   => composer UNSETTLED
#  10. pi pre-send dwell delivers after readiness        => composer SETTLED
#  11. pi post-stable recapture regressed to running    => refuse, no record
#  12. stopped cold start gets fresh-runtime readiness  => success, recorded
#  13. codex $0.000 (sub) footer classified ready        => success, recorded
#  14. codex $1.219 (sub) footer classified ready        => success, recorded
#  15. codex $1.219 (api) footer classified ready        => success, recorded
#  16. bare $1.219 (no marker) stays fail-closed         => refuse, no record
#  17. bare shell prompt stays fail-closed               => refuse, no record
#  18. vivi_pty $1.219 (sub) footer classified ready     => success, recorded
#  19. vivi_pty $1.219 (api) footer classified ready     => success, recorded
#  20. vivi_pty bare $1.219 stays fail-closed            => refuse, no record
#  21. shell-looking handle/note inert (no execution)    => success, recorded
#  22. no-handle pointer: assignment, not self-wake      => success, recorded
#
# Scenarios 21-22 cover the assignment-pointer wording fix: 21 proves the
# pointer template uses only ${VAR} interpolation (no backticks / $()), so a
# handle/note carrying shell metacharacters is delivered as inert composer text
# and never executed; 22 proves the no-handle pointer directs the recipient to
# list its own next open task (new vivi subcommand + --for <identity>), never
# to ring fleet-doorbell.
#
# Scenarios 13-17 cover the shell/tmux classifier (classify_tmux_text) for
# the nonzero-cost footer fix: a structured `$<amount> (sub|api)` Codex footer
# must classify as agent-idle for any nonnegative amount, while bare money and
# shell prompts stay fail-closed. Scenarios 18-20 cover the Python diagnostic
# classifier (classify_text inside classify_vivi_pty) which had the same loose
# `$0.` bug, driven through a fake vivi-pty.
#
# Scenarios 1-4 exercise the transition-aware /new path on a non-Pi agent
# (codex), because assignment_mode=new for Pi now recreates the role runtime
# instead of sending in-process /new (Pi's post-/new composer is unusable).
# Scenario 5 is the continue-mode P1 regression: a new handle under
# assignment_mode=continue skips preparation, so DID_PREPARE stays 0 and a
# general Pi pointer needs no acknowledgement. Scenario 6 proves the prepared
# ack gate still holds for compact. Scenarios 7-8 cover the Pi recreate path
# (success and failure) via the FLEET_RUNTIME_PY test seam.
# Scenarios 9-10 exercise the fresh-runtime readiness seam with a behavioral
# fake-tmux model: a pointer delivered before the readiness window matures is
# UNSETTLED (paste dropped / Enter ignored); the bounded pre-send dwell
# delivers after readiness -> SETTLED. Scenario 11 is the auditor-1 P1
# regression: a post-stable pre-send recapture regressed to running must refuse
# BEFORE typing the pointer and record nothing. Scenario 12 generalizes
# readiness to start-or-recreate: a stopped cold start (assignment_mode=
# continue, stopped) is a fresh runtime and gets the pre-send dwell too.
#
# Injection: the script zeros TMUX_BIN at startup, so we place a fake `tmux`
# on PATH (found via `command -v tmux`); PYTHON_BIN is honored from env.
# The fake tmux serves scripted pane snapshots from a tape file (one per
# capture-pane call; repeats the last line when exhausted) and records every
# send-keys call to a log. A fake fleet-runtime.py (Python) is injected via
# FLEET_RUNTIME_PY to drive the Pi recreate lifecycle.
#
# Run: bash scripts/test_fleet_doorbell.sh
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
DOORBELL="$SCRIPT_DIR/fleet-doorbell.sh"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
[[ -x "$DOORBELL" ]] || { echo "ERROR: doorbell not executable: $DOORBELL" >&2; exit 2; }
[[ -n "$PYTHON_BIN" && -x "$PYTHON_BIN" ]] || { echo "ERROR: python3 not found (set PYTHON_BIN)" >&2; exit 2; }

TMP="$(mktemp -d 2>/dev/null || mktemp -d -t fleetdoorbell)"
trap 'rm -rf "$TMP"' EXIT
FAKEBIN="$TMP/bin"
mkdir -p "$FAKEBIN" "$TMP/project/.vivi"
BASELINE="$TMP/project/.vivi/mind-baseline.json"
SENT="$TMP/sent.log"
TAPE="$TMP/tape"
CURSOR="$TMP/cursor"
# Behavioral fresh-runtime readiness model files for the pre-send
# stabilization seam (scenarios 9-12). FRESH_TS is stamped on start or
# restart; STARTED_MARKER flips has-session from stopped to up (cold start).
COMPOSER_VERDICT="$TMP/composer_verdict"
FRESH_TS="$TMP/fresh_ts"
STARTED_MARKER="$TMP/started_marker"
# vivi_pty classifier-regression seam: terminal contents the fake vivi-pty
# reports for `session diagnostic` (scenarios 18-20).
VPTY_CONTENTS="$TMP/vpty_contents"
READY_SEC="${READY_SEC:-0.5}"

# Pane snapshots (single-line; classify_tmux_text matches on the whole text).
IDLE='pi v0.80 (zai) glm-5.2 low 0.0%/1.0M (auto)'
CODEX_IDLE='codex › openai-codex ready'
RUNNING='Thinking… handling assignment'
NEW_DONE='New session started'   # differs from idle -> transition marker
COMPACT_DONE='Compacted session' # differs from idle -> transition marker
# Codex cost-footer snapshots: a structured `$<amount> (sub|api)` marker is
# the only money shape that classifies as agent-idle. Bare amounts and shell
# prompts must stay fail-closed (regressions for the nonzero-cost fix).
CODEX_COST_SUB_ZERO='$0.000 (sub) gpt-5.5 • high'
CODEX_COST_SUB_NONZERO='$1.219 (sub) gpt-5.5 • high'
CODEX_COST_API_NONZERO='$1.219 (api) gpt-5.5 • high'
CODEX_COST_BARE='$1.219'
SHELL_PROMPT='%'

# fleet.json writer: hand-1 with a configurable agent + assignment_mode.
# Scenarios 1-4 use codex/new (/new transition path); 5 continue; 6 compact;
# 7-8 pi/new (recreate path). Unquoted heredoc so $agent/$mode expand.
write_fleet_config() {
  local mode="$1" agent="${2:-pi}"
  cat > "$TMP/project/.vivi/fleet.json" <<JSON
{
  "fleet_id": "test",
  "hands": {
    "hand-1": {
      "tmux_target": "test:hand-1.1",
      "agent": "$agent",
      "assignment_mode": "$mode"
    }
  }
}
JSON
}

# fleet.json writer: hand-1 backed by vivi_pty (codex continue). The Python
# diagnostic classifier (classify_text) is exercised only when harness_state
# is not a decisive driver state, so the fake vivi-pty reports
# harness_state=unknown and the regex decides readiness from terminal contents.
write_fleet_config_vpty() {
  local mode="$1" agent="${2:-codex}"
  cat > "$TMP/project/.vivi/fleet.json" <<JSON
{
  "fleet_id": "test",
  "hands": {
    "hand-1": {
      "agent": "$agent",
      "assignment_mode": "$mode",
      "runtime": {
        "kind": "vivi_pty",
        "session_id": "hand-1",
        "socket": "$TMP/vpty.sock"
      }
    }
  }
}
JSON
}

# Fake tmux: dispatches on $1; capture-pane returns the next tape line.
cat > "$FAKEBIN/tmux" <<'SH'
#!/usr/bin/env bash
case "${1:-}" in
  has-session)
    # Cold-start model: report stopped (exit 1) until the runtime is started,
    # but only when SIMULATE_STOPPED is set (other scenarios stay always-up).
    if [ -n "${SIMULATE_STOPPED:-}" ] && [ ! -f "${STARTED_MARKER:-}" ]; then exit 1; fi
    exit 0
    ;;
  capture-pane)
    n="$(cat "$CURSOR_FILE" 2>/dev/null || echo 0)"
    line="$(sed -n "$((n+1))p" "$TAPE_FILE" 2>/dev/null || true)"
    if [ -z "$line" ]; then
      total="$(awk 'END{print NR}' "$TAPE_FILE" 2>/dev/null || echo 1)"
      line="$(sed -n "${total}p" "$TAPE_FILE" 2>/dev/null || true)"
    fi
    printf '%s\n' "$line"
    echo "$((n+1))" > "$CURSOR_FILE"
    exit 0
    ;;
  send-keys)
    printf 'SEND: %s\n' "$*" >> "$SENT_FILE"
    # Behavioral fresh-runtime readiness model for the pre-send stabilization
    # seam. A freshly started or recreated runtime paints idle chrome before
    # its input handling is wired, so a pointer delivered then has its paste
    # dropped / Enter ignored (delivery started before readiness).
    # fake-fleet-runtime records the fresh epoch (start or restart); if the
    # paste (delivery start) lands within READY_SEC of the bring-up, model the
    # composer UNSETTLED; after readiness, SETTLED. The fix is the pre-send
    # dwell, not a paste->Enter gap.
    if [ -n "${COMPOSER_VERDICT_FILE:-}" ] && [ -f "${FRESH_TS_FILE:-}" ]; then
      case " $* " in
        *" -l "*)
          "${PYTHON_BIN:-python3}" -c '
import sys, time
try:
    fresh = float(open(sys.argv[1]).read())
except Exception:
    fresh = 0.0
gap = time.time() - fresh
ready = float(sys.argv[3])
verdict = "SETTLED" if gap >= ready else "UNSETTLED"
with open(sys.argv[2], "a") as fh:
    fh.write("COMPOSER since_fresh=%.3f ready_sec=%s verdict=%s\n" % (gap, sys.argv[3], verdict))
' "${FRESH_TS_FILE}" "${COMPOSER_VERDICT_FILE}" "${READY_SEC:-0.5}" 2>/dev/null || true
          ;;
      esac
    fi
    exit 0
    ;;
  *) exit 0 ;;
esac
SH
chmod +x "$FAKEBIN/tmux"

# Fake vivi-pty for the Python classifier regressions (scenarios 18-20).
# `session diagnostic` emits JSON whose terminal.contents come from
# $VPTY_CONTENTS_FILE with harness_state=unknown (forces the classify_text
# regex path); `terminal write|key` record to $SENT_FILE like the fake tmux.
cat > "$FAKEBIN/vivi-pty" <<'SH'
#!/usr/bin/env bash
case "${1:-}" in
  session)
    if [ "${2:-}" = "diagnostic" ]; then
      "${PYTHON_BIN:-python3}" -c '
import json, os
contents = ""
try:
    with open(os.environ["VPTY_CONTENTS_FILE"]) as fh:
        contents = fh.read()
except Exception:
    contents = ""
print(json.dumps({"harness_state": "unknown", "terminal": {"contents": contents}}))
'
    fi
    exit 0
    ;;
  terminal)
    printf 'SEND: %s\n' "$*" >> "$SENT_FILE"
    exit 0
    ;;
  *) exit 0 ;;
esac
SH
chmod +x "$FAKEBIN/vivi-pty"

# Fake fleet-runtime.py (Python; invoked via PYTHON_BIN through the
# FLEET_RUNTIME_PY seam): logs the action argv to $RESTART_LOG and exits per
# $FLEET_RUNTIME_EXIT. Drives the Pi recreate lifecycle in scenarios 7-8.
cat > "$FAKEBIN/fake-fleet-runtime" <<'PY'
import os, sys, time
log = os.environ.get("RESTART_LOG")
if log:
    try:
        with open(log, "a") as fh:
            fh.write("RUNTIME " + " ".join(sys.argv[1:]) + "\n")
    except OSError:
        pass
# Model a fresh-runtime bring-up (start or restart): record the epoch so the
# fake tmux can gate delivery readiness on time-since-fresh (the post-start /
# post-recreate readiness race). start also flips has-session from stopped.
ts = os.environ.get("FRESH_TS_FILE")
if ts and ("restart" in sys.argv[1:] or "start" in sys.argv[1:]):
    try:
        with open(ts, "w") as fh:
            fh.write(repr(time.time()))
    except OSError:
        pass
started = os.environ.get("STARTED_MARKER")
if started and "start" in sys.argv[1:]:
    try:
        open(started, "w").write("1")
    except OSError:
        pass
sys.exit(int(os.environ.get("FLEET_RUNTIME_EXIT", "0")))
PY

pass=0
fail=0
ok()   { echo "ok   - $1"; pass=$((pass+1)); }
notok(){ echo "FAIL - $1"; fail=$((fail+1)); }

# Reset per-scenario state and write a fresh fleet.json (mode + agent).
# Reset per-scenario state. Third arg selects the backing runtime kind
# (tmux default -> write_fleet_config; vivi_pty -> write_fleet_config_vpty).
reset_state() {
  rm -f "$BASELINE" "$SENT" "$CURSOR" "$COMPOSER_VERDICT" "$FRESH_TS" "$STARTED_MARKER" "$VPTY_CONTENTS"
  : > "$SENT"
  echo "0" > "$CURSOR"
  if [ "${3:-tmux}" = "vivi_pty" ]; then
    write_fleet_config_vpty "${1:-new}" "${2:-codex}"
  else
    write_fleet_config "${1:-new}" "${2:-pi}"
  fi
}
write_tape() { : > "$TAPE"; local ln; for ln in "$@"; do printf '%s\n' "$ln" >> "$TAPE"; done; }
write_vpty_contents() { printf '%s\n' "$1" > "$VPTY_CONTENTS"; }

run_doorbell() {
  local handle="$1"; shift
  RUN_ERR="$TMP/err.log"
  # Default stabilization small for the legacy recreate scenario (7); the
  # readiness scenarios export a larger FLEET_DOORBELL_STABLE_WINDOW_SEC to
  # exercise the pre-send dwell that clears the fresh-runtime readiness window.
  local stable="${FLEET_DOORBELL_STABLE_WINDOW_SEC:-0.1}"
  # Build the doorbell argv. --handle is omitted when empty so the no-handle
  # branch is exercised (the script rejects --handle "" as "requires a value").
  local argv=(--project "$TMP/project" --role hand-1)
  if [[ -n "$handle" ]]; then
    argv+=(--handle "$handle")
  fi
  set +e
  RUN_OUT="$(env PATH="$FAKEBIN:$PATH" \
    PYTHON_BIN="$PYTHON_BIN" \
    TAPE_FILE="$TAPE" CURSOR_FILE="$CURSOR" SENT_FILE="$SENT" \
    COMPOSER_VERDICT_FILE="$COMPOSER_VERDICT" FRESH_TS_FILE="$FRESH_TS" READY_SEC="$READY_SEC" \
    VPTY_CONTENTS_FILE="$VPTY_CONTENTS" \
    FLEET_DOORBELL_PREPARE_TIMEOUT_SEC=3 \
    FLEET_DOORBELL_TRANSITION_TIMEOUT_SEC=1 \
    FLEET_DOORBELL_SUBMIT_ACK_TIMEOUT_SEC=2 \
    FLEET_DOORBELL_STABLE_WINDOW_SEC="$stable" \
    ${FLEET_RUNTIME_PY:+FLEET_RUNTIME_PY="$FLEET_RUNTIME_PY"} \
    ${RESTART_LOG:+RESTART_LOG="$RESTART_LOG"} \
    ${FLEET_RUNTIME_EXIT:+FLEET_RUNTIME_EXIT="$FLEET_RUNTIME_EXIT"} \
    ${SIMULATE_STOPPED:+SIMULATE_STOPPED=1 STARTED_MARKER="$STARTED_MARKER"} \
    bash "$DOORBELL" "${argv[@]}" "$@" 2>"$RUN_ERR")"
  RUN_CODE=$?
  set -e
}

baseline_has_handle() { [[ -f "$BASELINE" ]] && grep -q "$1" "$BASELINE"; }
sent_has() { grep -q -- "$1" "$SENT"; }
# Assert the assignment-pointer paste precedes the Enter submit in the SEND log.
ordering_ok() {
  local paste_ln enter_ln
  paste_ln="$(grep -n 'Assignment for' "$1" | head -1 | cut -d: -f1)"
  enter_ln="$(grep -n 'Enter$' "$1" | head -1 | cut -d: -f1)"
  [[ -n "$paste_ln" && -n "$enter_ln" && "$paste_ln" -lt "$enter_ln" ]]
}
# Last composer verdict from the behavioral fresh-runtime readiness model.
verdict_last() { tail -1 "$COMPOSER_VERDICT" 2>/dev/null || true; }

# ── Scenario 1: stale-idle classifier race (codex /new) => refuse ───────
reset_state new codex
write_tape "$CODEX_IDLE"   # pane never changes after /new (stale idle forever)
run_doorbell aa110001
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa110001 \
   && sent_has '/new' \
   && ! sent_has 'Assignment for hand-1'; then
  ok "codex stale-idle race refused (exit 1), no record, /new sent, pointer NOT sent"
else
  notok "codex stale-idle race: code=$RUN_CODE baseline=$(baseline_has_handle aa110001 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 2: delayed /new transition (codex) => success ──────────────
reset_state new codex
write_tape "$CODEX_IDLE" "$CODEX_IDLE" "$CODEX_IDLE" "$CODEX_IDLE" "$CODEX_IDLE" "$CODEX_IDLE" "$NEW_DONE" "$CODEX_IDLE" "$CODEX_IDLE" "$RUNNING"
run_doorbell aa220002
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa220002 \
   && sent_has '/new' \
   && sent_has 'Assignment for hand-1'; then
  ok "codex delayed /new transition succeeded after stale polls; wake recorded"
else
  notok "codex delayed transition: code=$RUN_CODE baseline=$(baseline_has_handle aa220002 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 3: successful fresh readiness (codex /new) => success ──────
reset_state new codex
write_tape "$CODEX_IDLE" "$CODEX_IDLE" "$CODEX_IDLE" "$CODEX_IDLE" "$NEW_DONE" "$CODEX_IDLE" "$CODEX_IDLE" "$RUNNING"
run_doorbell aa330003
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa330003 \
   && sent_has 'Assignment for hand-1'; then
  ok "codex fresh readiness succeeded promptly; wake recorded"
else
  notok "codex fresh readiness: code=$RUN_CODE baseline=$(baseline_has_handle aa330003 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 4: pointer never acknowledged (codex /new) => refuse ───────
reset_state new codex
write_tape "$CODEX_IDLE" "$CODEX_IDLE" "$CODEX_IDLE" "$CODEX_IDLE" "$NEW_DONE" "$CODEX_IDLE" "$CODEX_IDLE"
run_doorbell aa440004
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa440004 \
   && sent_has 'Assignment for hand-1'; then
  ok "codex pointer never acknowledged refused (exit 1), no record, pointer was sent"
else
  notok "codex pointer never ack: code=$RUN_CODE baseline=$(baseline_has_handle aa440004 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 5: continue + new handle, no --no-prepare (pi) => success (P1)
reset_state continue pi
write_tape "$IDLE"
run_doorbell aa550005
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa550005 \
   && sent_has 'Assignment for hand-1' \
   && ! sent_has '/new' \
   && ! sent_has '/compact'; then
  ok "continue + new handle preserved (no /new|/compact, no forced ack); wake recorded"
else
  notok "continue + new handle: code=$RUN_CODE baseline=$(baseline_has_handle aa550005 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 6: pointer never acknowledged (pi compact) => refuse ───────
reset_state compact pi
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$COMPACT_DONE" "$IDLE" "$IDLE"
run_doorbell aa660006
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa660006 \
   && sent_has '/compact' \
   && sent_has 'Assignment for hand-1'; then
  ok "compact pointer never acknowledged refused (exit 1), no record, pointer was sent"
else
  notok "compact never ack: code=$RUN_CODE baseline=$(baseline_has_handle aa660006 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 7: pi new recreates runtime (no /new) => success ───────────
# Pi assignment_mode=new on an existing runtime must recreate the role runtime
# (the "new or recreate" contract), not send /new, then pointer+ack records.
RESTART_LOG="$TMP/restart7.log"; rm -f "$RESTART_LOG"
reset_state new pi
export FLEET_RUNTIME_PY="$FAKEBIN/fake-fleet-runtime" RESTART_LOG FLEET_RUNTIME_EXIT=0
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$RUNNING"
run_doorbell aa770007
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa770007 \
   && sent_has 'Assignment for hand-1' \
   && ! sent_has '/new' \
   && [[ -f "$RESTART_LOG" ]] && grep -q -e '--role hand-1 restart' "$RESTART_LOG"; then
  ok "pi new recreated runtime (no /new), restart called, pointer acked, wake recorded"
else
  notok "pi new recreate: code=$RUN_CODE baseline=$(baseline_has_handle aa770007 && echo y || echo n) restart=$(test -f "$RESTART_LOG" && echo y || echo n) err=$(cat "$RUN_ERR")"
fi
unset FLEET_RUNTIME_PY RESTART_LOG FLEET_RUNTIME_EXIT

# ── Scenario 8: pi new recreate failure => refuse, no wake record ───────
# recreate failure (fleet-runtime restart nonzero) refuses and records nothing.
RESTART_LOG="$TMP/restart8.log"; rm -f "$RESTART_LOG"
reset_state new pi
export FLEET_RUNTIME_PY="$FAKEBIN/fake-fleet-runtime" RESTART_LOG FLEET_RUNTIME_EXIT=1
write_tape "$IDLE" "$IDLE" "$IDLE"
run_doorbell aa880008
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa880008 \
   && ! sent_has 'Assignment for hand-1' \
   && ! sent_has '/new' \
   && [[ -f "$RESTART_LOG" ]]; then
  ok "pi new recreate failure refused (exit 1), no record, restart attempted, no /new"
else
  notok "pi recreate fail: code=$RUN_CODE baseline=$(baseline_has_handle aa880008 && echo y || echo n) restart=$(test -f "$RESTART_LOG" && echo y || echo n) err=$(cat "$RUN_ERR")"
fi
unset FLEET_RUNTIME_PY RESTART_LOG FLEET_RUNTIME_EXIT

# ── Scenario 9: pointer delivered before recreate readiness (bug) ─────
# Behavioral readiness seam: a freshly recreated runtime paints idle chrome
# before input handling is wired. With only a token stabilization (0.1s) the
# pointer is delivered inside the readiness window -> the fake models the
# composer UNSETTLED (paste dropped / Enter ignored). This reproduces the live
# failure mode (a 0.8s paste->Enter gap could not rescue a paste delivered
# before readiness). Delivery-before-readiness, not Enter timing.
RESTART_LOG="$TMP/restart9.log"; rm -f "$RESTART_LOG"
reset_state new pi
export FLEET_RUNTIME_PY="$FAKEBIN/fake-fleet-runtime" RESTART_LOG FLEET_RUNTIME_EXIT=0
export FLEET_DOORBELL_STABLE_WINDOW_SEC=0.1
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$RUNNING"
run_doorbell aa990009
unset FLEET_DOORBELL_STABLE_WINDOW_SEC
unset FLEET_RUNTIME_PY RESTART_LOG FLEET_RUNTIME_EXIT
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa990009 \
   && sent_has 'Assignment for hand-1' \
   && ordering_ok "$SENT" \
   && [[ "$(verdict_last)" == *verdict=UNSETTLED* ]]; then
  ok "pi pointer delivered before recreate readiness (0.1s dwell) -> composer UNSETTLED (bug reproduced)"
else
  notok "pi pre-readiness: code=$RUN_CODE verdict=$(verdict_last) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 10: pre-send dwell delivers after recreate readiness (fix) ─
# The bounded pre-send stabilization dwells past the readiness window before
# send_line, so delivery starts after readiness -> composer SETTLED, pointer
# submitted + recorded. Passes because delivery starts after readiness, NOT
# because Enter is delayed after paste (submit delay stays at the 0.05
# default). The recreate + ack end-to-end path (scenario 7) stays green.
RESTART_LOG="$TMP/restart10.log"; rm -f "$RESTART_LOG"
reset_state new pi
export FLEET_RUNTIME_PY="$FAKEBIN/fake-fleet-runtime" RESTART_LOG FLEET_RUNTIME_EXIT=0
export FLEET_DOORBELL_STABLE_WINDOW_SEC=0.8
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$RUNNING"
run_doorbell aa100010
unset FLEET_DOORBELL_STABLE_WINDOW_SEC
unset FLEET_RUNTIME_PY RESTART_LOG FLEET_RUNTIME_EXIT
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa100010 \
   && sent_has 'Assignment for hand-1' \
   && ordering_ok "$SENT" \
   && [[ "$(verdict_last)" == *verdict=SETTLED* ]]; then
  ok "pi pre-send dwell (0.8s) delivered after recreate readiness -> composer SETTLED; recorded"
else
  notok "pi post-readiness: code=$RUN_CODE verdict=$(verdict_last) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 11: post-stable pre-send recapture regressed to running ─────
# auditor-1 P1 (882f96d9): after the stable readiness window, the final
# pre-send recapture must be input-accepting. A regression to running at the
# recapture must refuse BEFORE typing the pointer and record nothing. The
# recreate ran; the pointer never did.
RESTART_LOG="$TMP/restart11.log"; rm -f "$RESTART_LOG"
reset_state new pi
export FLEET_RUNTIME_PY="$FAKEBIN/fake-fleet-runtime" RESTART_LOG FLEET_RUNTIME_EXIT=0
export FLEET_DOORBELL_STABLE_WINDOW_SEC=0.3
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$RUNNING"
run_doorbell aa110011
unset FLEET_DOORBELL_STABLE_WINDOW_SEC
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa110011 \
   && ! sent_has 'Assignment for hand-1' \
   && [[ -f "$RESTART_LOG" ]] && grep -q -e '--role hand-1 restart' "$RESTART_LOG"; then
  ok "pi post-stable recapture regressed to running refused (exit 1), no pointer, no record; recreate ran"
else
  notok "pi pre-send regression: code=$RUN_CODE baseline=$(baseline_has_handle aa110011 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi
unset FLEET_RUNTIME_PY RESTART_LOG FLEET_RUNTIME_EXIT

# ── Scenario 12: stopped cold start gets fresh-runtime readiness ─────────
# Fresh-runtime readiness is generalized to start-or-recreate (DID_FRESH). A
# stopped runtime started via the cold-start path (assignment_mode=continue,
# stopped, simulated via SIMULATE_STOPPED) is a fresh runtime: it gets the
# pre-send dwell, so delivery starts after readiness -> SETTLED. Catches a
# regression where cold start does not set DID_FRESH (no dwell -> UNSETTLED).
RESTART_LOG="$TMP/restart12.log"; rm -f "$RESTART_LOG"
reset_state continue pi
export FLEET_RUNTIME_PY="$FAKEBIN/fake-fleet-runtime" RESTART_LOG FLEET_RUNTIME_EXIT=0
export FLEET_DOORBELL_STABLE_WINDOW_SEC=0.8 SIMULATE_STOPPED=1
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE"
run_doorbell aa120012
unset FLEET_DOORBELL_STABLE_WINDOW_SEC SIMULATE_STOPPED
unset FLEET_RUNTIME_PY RESTART_LOG FLEET_RUNTIME_EXIT
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa120012 \
   && sent_has 'Assignment for hand-1' \
   && ordering_ok "$SENT" \
   && [[ -f "$STARTED_MARKER" ]] \
   && [[ "$(verdict_last)" == *verdict=SETTLED* ]]; then
  ok "pi stopped cold start got fresh-runtime readiness (dwell) -> composer SETTLED; recorded"
else
  notok "pi cold start: code=$RUN_CODE started=$(test -f "$STARTED_MARKER" && echo y || echo n) verdict=$(verdict_last) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 13: codex $0.000 (sub) footer classified ready => success ──
# Structured cost footer with a zero amount + (sub) marker must still classify
# as agent-idle after the loose $0. matcher is replaced by the structured
# $<amount> (sub|api) pattern (regression guard for the zero case).
reset_state continue codex
write_tape "$CODEX_COST_SUB_ZERO"
run_doorbell aa130013
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa130013 \
   && sent_has 'Assignment for hand-1'; then
  ok "codex \$0.000 (sub) footer classified ready; wake recorded"
else
  notok "codex \$0.000 (sub): code=$RUN_CODE baseline=$(baseline_has_handle aa130013 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 14: codex $1.219 (sub) footer classified ready => success ──
# THE BUG: a nonzero Codex cost footer ($1.219 (sub)) classified unready
# because both classifiers only matched loose $0. The doorbell failed closed
# and required a runtime restart; a fresh $0.000 then worked. The structured
# pattern now matches any nonnegative amount, so this pane is agent-idle.
reset_state continue codex
write_tape "$CODEX_COST_SUB_NONZERO"
run_doorbell aa140014
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa140014 \
   && sent_has 'Assignment for hand-1'; then
  ok "codex \$1.219 (sub) nonzero footer classified ready; wake recorded"
else
  notok "codex \$1.219 (sub): code=$RUN_CODE baseline=$(baseline_has_handle aa140014 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 15: codex $1.219 (api) footer classified ready => success ──
# The structured pattern accepts the documented (api) marker as well as (sub).
reset_state continue codex
write_tape "$CODEX_COST_API_NONZERO"
run_doorbell aa150015
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa150015 \
   && sent_has 'Assignment for hand-1'; then
  ok "codex \$1.219 (api) footer classified ready; wake recorded"
else
  notok "codex \$1.219 (api): code=$RUN_CODE baseline=$(baseline_has_handle aa150015 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 16: bare $1.219 (no marker) stays fail-closed => refuse ────
# Removing the loose $0. matcher must NOT broaden the classifier to arbitrary
# money. A bare nonzero amount with no (sub|api) marker is unrecognized ->
# unready -> refuse, no record, no pointer. Fail-closed for money output and
# shell-injection risk.
reset_state continue codex
write_tape "$CODEX_COST_BARE"
run_doorbell aa160016
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa160016 \
   && ! sent_has 'Assignment for hand-1'; then
  ok "codex bare \$1.219 (no marker) refused (exit 1), no record, no pointer"
else
  notok "codex bare \$1.219: code=$RUN_CODE baseline=$(baseline_has_handle aa160016 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 17: bare shell prompt stays fail-closed => refuse ──────────
# A classic shell prompt must never pass the agent-idle classifier; the
# doorbell refuses rather than typing a pointer into a shell.
reset_state continue codex
write_tape "$SHELL_PROMPT"
run_doorbell aa170017
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa170017 \
   && ! sent_has 'Assignment for hand-1'; then
  ok "bare shell prompt (%) refused (exit 1), no record, no pointer"
else
  notok "shell prompt: code=$RUN_CODE baseline=$(baseline_has_handle aa170017 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 18: vivi_pty $1.219 (sub) footer classified ready => success ─
# The Python diagnostic classifier (classify_text inside classify_vivi_pty)
# had the same loose $0. bug. The fake vivi-pty reports harness_state=unknown
# so classify_text decides readiness from terminal contents; the structured
# pattern now matches the nonzero footer through the vivi_pty code path too.
reset_state continue codex vivi_pty
write_vpty_contents "$CODEX_COST_SUB_NONZERO"
run_doorbell aa180018
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa180018 \
   && sent_has 'Assignment for hand-1'; then
  ok "vivi_pty \$1.219 (sub) nonzero footer classified ready; wake recorded"
else
  notok "vivi_pty \$1.219 (sub): code=$RUN_CODE baseline=$(baseline_has_handle aa180018 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 19: vivi_pty $1.219 (api) footer classified ready => success ─
reset_state continue codex vivi_pty
write_vpty_contents "$CODEX_COST_API_NONZERO"
run_doorbell aa190019
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa190019 \
   && sent_has 'Assignment for hand-1'; then
  ok "vivi_pty \$1.219 (api) footer classified ready; wake recorded"
else
  notok "vivi_pty \$1.219 (api): code=$RUN_CODE baseline=$(baseline_has_handle aa190019 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 20: vivi_pty bare $1.219 stays fail-closed => refuse ────────
# The Python path must also keep bare money fail-closed (no marker -> unready).
reset_state continue codex vivi_pty
write_vpty_contents "$CODEX_COST_BARE"
run_doorbell aa200020
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa200020 \
   && ! sent_has 'Assignment for hand-1'; then
  ok "vivi_pty bare \$1.219 (no marker) refused (exit 1), no record, no pointer"
else
  notok "vivi_pty bare \$1.219: code=$RUN_CODE baseline=$(baseline_has_handle aa200020 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 21: shell-looking handle/note are inert composer text ──────
# The pointer template must use only ${VAR} interpolation (no backticks /
# $()), so a handle or note carrying shell metacharacters cannot become
# executable syntax: it is delivered as inert composer text and never
# executed. Two canaries would be created if any command substitution ran;
# both must stay absent, while the literal injection text is present verbatim
# in the SEND log on a single line (paste precedes Enter).
reset_state continue pi
write_tape "$IDLE"
CANARY_H="$TMP/canary21h"; rm -f "$CANARY_H"
CANARY_N="$TMP/canary21n"; rm -f "$CANARY_N"
# If the template ever command-substituted these, the canaries would appear.
INJ_HANDLE='$(touch '"$CANARY_H"')'
INJ_NOTE='`touch '"$CANARY_N"'`; rm -rf / #'
run_doorbell "$INJ_HANDLE" --note "$INJ_NOTE"
if [[ "$RUN_CODE" -eq 0 ]] \
   && [[ ! -e "$CANARY_H" && ! -e "$CANARY_N" ]] \
   && sent_has 'Assignment for hand-1' \
   && grep -qF -- 'touch '"$CANARY_H" "$SENT" \
   && grep -qF -- 'touch '"$CANARY_N" "$SENT" \
   && ordering_ok "$SENT"; then
  ok "shell-looking handle/note delivered inert (no execution), single line; recorded"
else
  notok "injection: code=$RUN_CODE canaryH=$([ -e "$CANARY_H" ] && echo EXISTS || echo no) canaryN=$([ -e "$CANARY_N" ] && echo EXISTS || echo no) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 22: no-handle pointer is an assignment, not a self-wake ────
# Without a handle the pointer must direct the recipient to list/show its OWN
# next open task (new assignment wording with the correct vivi subcommand and
# --for <identity>), never to ring fleet-doorbell. An empty handle arg makes
# run_doorbell omit --handle entirely (the script rejects --handle ""),
# selecting the no-handle branch.
reset_state continue pi
write_tape "$IDLE"
run_doorbell ""   # empty handle -> no-handle branch
if [[ "$RUN_CODE" -eq 0 ]] \
   && [[ -f "$BASELINE" ]] \
   && sent_has 'Assignment for hand-1' \
   && sent_has 'do NOT run fleet-doorbell' \
   && sent_has 'vivi task list' \
   && grep -qF -- '--for hand-1' "$SENT" \
   && ! sent_has 'Bag: show' \
   && ! sent_has ' HAND WAKE' \
   && ordering_ok "$SENT"; then
  ok "no-handle pointer directs recipient to list own tasks (assignment, not self-wake)"
else
  notok "no-handle: code=$RUN_CODE baseline=$([ -f "$BASELINE" ] && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

echo "---"
echo "pass=$pass fail=$fail"
[[ "$fail" -eq 0 ]]
