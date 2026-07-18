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
#   9. pi send_line too-fast Enter (0.05s)                => composer UNSETTLED
#  10. pi send_line default delay (0.8s)                  => composer SETTLED
#
# Scenarios 1-4 exercise the transition-aware /new path on a non-Pi agent
# (codex), because assignment_mode=new for Pi now recreates the role runtime
# instead of sending in-process /new (Pi's post-/new composer is unusable).
# Scenario 5 is the continue-mode P1 regression: a new handle under
# assignment_mode=continue skips preparation, so DID_PREPARE stays 0 and a
# general Pi pointer needs no acknowledgement. Scenario 6 proves the prepared
# ack gate still holds for compact. Scenarios 7-8 cover the Pi recreate path
# (success and failure) via the FLEET_RUNTIME_PY test seam.
# Scenarios 9-10 exercise the send_line paste-settle timing seam with a
# behavioral fake-tmux composer model: a too-fast Enter (0.05s) leaves the
# pointer UNSETTLED in the composer, while the selected Pi default (0.8s)
# settles and submits.
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
# Behavioral paste-settle model files for the send_line timing seam (scenarios 9-10).
COMPOSER_VERDICT="$TMP/composer_verdict"
PASTE_TS="$TMP/paste_ts"
PI_SETTLE_SEC="${PI_SETTLE_SEC:-0.5}"

# Pane snapshots (single-line; classify_tmux_text matches on the whole text).
IDLE='pi v0.80 (zai) glm-5.2 low 0.0%/1.0M (auto)'
CODEX_IDLE='codex › openai-codex ready'
RUNNING='Thinking… handling HAND WAKE'
NEW_DONE='New session started'   # differs from idle -> transition marker
COMPACT_DONE='Compacted session' # differs from idle -> transition marker

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

# Fake tmux: dispatches on $1; capture-pane returns the next tape line.
cat > "$FAKEBIN/tmux" <<'SH'
#!/usr/bin/env bash
case "${1:-}" in
  has-session) exit 0 ;;
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
    # Behavioral paste-settle model for the send_line ordering/timing seam.
    # send_line does `send-keys -l <text>` (paste), `sleep <delay>`, then
    # `send-keys Enter` (submit). Model Pi's fresh-runtime paste-settling: an
    # Enter within PI_SETTLE_SEC of the paste leaves the wake pointer unsent
    # in the composer (the observed pointer-loss race). Active only when the
    # timing files are configured.
    if [ -n "${COMPOSER_VERDICT_FILE:-}" ]; then
      case " $* " in
        *" -l "*)
          "${PYTHON_BIN:-python3}" -c 'import sys,time; open(sys.argv[1],"w").write(repr(time.time()))' "${PASTE_TS_FILE:-/dev/null}" 2>/dev/null || true
          ;;
        *" Enter "*)
          if [ -f "${PASTE_TS_FILE:-}" ]; then
            "${PYTHON_BIN:-python3}" -c '
import sys, time
try:
    paste = float(open(sys.argv[1]).read())
except Exception:
    paste = 0.0
gap = time.time() - paste
settle = float(sys.argv[3])
verdict = "SETTLED" if gap >= settle else "UNSETTLED"
with open(sys.argv[2], "a") as fh:
    fh.write("COMPOSER gap=%.3f verdict=%s\n" % (gap, verdict))
' "${PASTE_TS_FILE}" "${COMPOSER_VERDICT_FILE}" "${PI_SETTLE_SEC:-0.5}" 2>/dev/null || true
          fi
          ;;
      esac
    fi
    exit 0
    ;;
  *) exit 0 ;;
esac
SH
chmod +x "$FAKEBIN/tmux"

# Fake fleet-runtime.py (Python; invoked via PYTHON_BIN through the
# FLEET_RUNTIME_PY seam): logs the action argv to $RESTART_LOG and exits per
# $FLEET_RUNTIME_EXIT. Drives the Pi recreate lifecycle in scenarios 7-8.
cat > "$FAKEBIN/fake-fleet-runtime" <<'PY'
import os, sys
log = os.environ.get("RESTART_LOG")
if log:
    try:
        with open(log, "a") as fh:
            fh.write("RUNTIME " + " ".join(sys.argv[1:]) + "\n")
    except OSError:
        pass
sys.exit(int(os.environ.get("FLEET_RUNTIME_EXIT", "0")))
PY

pass=0
fail=0
ok()   { echo "ok   - $1"; pass=$((pass+1)); }
notok(){ echo "FAIL - $1"; fail=$((fail+1)); }

# Reset per-scenario state and write a fresh fleet.json (mode + agent).
reset_state() {
  rm -f "$BASELINE" "$SENT" "$CURSOR" "$COMPOSER_VERDICT" "$PASTE_TS"
  : > "$SENT"
  echo "0" > "$CURSOR"
  write_fleet_config "${1:-new}" "${2:-pi}"
}
write_tape() { : > "$TAPE"; local ln; for ln in "$@"; do printf '%s\n' "$ln" >> "$TAPE"; done; }

run_doorbell() {
  local handle="$1"; shift
  RUN_ERR="$TMP/err.log"
  set +e
  RUN_OUT="$(env PATH="$FAKEBIN:$PATH" \
    PYTHON_BIN="$PYTHON_BIN" \
    TAPE_FILE="$TAPE" CURSOR_FILE="$CURSOR" SENT_FILE="$SENT" \
    COMPOSER_VERDICT_FILE="$COMPOSER_VERDICT" PASTE_TS_FILE="$PASTE_TS" PI_SETTLE_SEC="$PI_SETTLE_SEC" \
    FLEET_DOORBELL_PREPARE_TIMEOUT_SEC=3 \
    FLEET_DOORBELL_TRANSITION_TIMEOUT_SEC=1 \
    FLEET_DOORBELL_SUBMIT_ACK_TIMEOUT_SEC=2 \
    ${FLEET_RUNTIME_PY:+FLEET_RUNTIME_PY="$FLEET_RUNTIME_PY"} \
    ${RESTART_LOG:+RESTART_LOG="$RESTART_LOG"} \
    ${FLEET_RUNTIME_EXIT:+FLEET_RUNTIME_EXIT="$FLEET_RUNTIME_EXIT"} \
    ${FLEET_DOORBELL_SUBMIT_DELAY_SEC:+FLEET_DOORBELL_SUBMIT_DELAY_SEC="$FLEET_DOORBELL_SUBMIT_DELAY_SEC"} \
    bash "$DOORBELL" --project "$TMP/project" --role hand-1 --handle "$handle" "$@" 2>"$RUN_ERR")"
  RUN_CODE=$?
  set -e
}

baseline_has_handle() { [[ -f "$BASELINE" ]] && grep -q "$1" "$BASELINE"; }
sent_has() { grep -q -- "$1" "$SENT"; }
# Assert the HAND WAKE paste precedes the Enter submit in the SEND log ordering.
ordering_ok() {
  local paste_ln enter_ln
  paste_ln="$(grep -n 'HAND WAKE' "$1" | head -1 | cut -d: -f1)"
  enter_ln="$(grep -n 'Enter$' "$1" | head -1 | cut -d: -f1)"
  [[ -n "$paste_ln" && -n "$enter_ln" && "$paste_ln" -lt "$enter_ln" ]]
}
# Last composer verdict from the behavioral paste-settle model.
verdict_last() { tail -1 "$COMPOSER_VERDICT" 2>/dev/null || true; }

# ── Scenario 1: stale-idle classifier race (codex /new) => refuse ───────
reset_state new codex
write_tape "$CODEX_IDLE"   # pane never changes after /new (stale idle forever)
run_doorbell aa110001
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa110001 \
   && sent_has '/new' \
   && ! sent_has 'HAND WAKE hand-1'; then
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
   && sent_has 'HAND WAKE hand-1'; then
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
   && sent_has 'HAND WAKE hand-1'; then
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
   && sent_has 'HAND WAKE hand-1'; then
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
   && sent_has 'HAND WAKE hand-1' \
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
   && sent_has 'HAND WAKE hand-1'; then
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
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$RUNNING"
run_doorbell aa770007
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa770007 \
   && sent_has 'HAND WAKE hand-1' \
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
   && ! sent_has 'HAND WAKE hand-1' \
   && ! sent_has '/new' \
   && [[ -f "$RESTART_LOG" ]]; then
  ok "pi new recreate failure refused (exit 1), no record, restart attempted, no /new"
else
  notok "pi recreate fail: code=$RUN_CODE baseline=$(baseline_has_handle aa880008 && echo y || echo n) restart=$(test -f "$RESTART_LOG" && echo y || echo n) err=$(cat "$RUN_ERR")"
fi
unset FLEET_RUNTIME_PY RESTART_LOG FLEET_RUNTIME_EXIT

# ── Scenario 9: pi send_line too-fast Enter reproduces unsent composer ──
# Behavioral timing seam: with the old too-fast default (0.05s override) Enter
# lands inside Pi's paste-settling window, so the fake models the wake pointer
# as UNSETTLED — it sits unsent in the composer (the pointer-loss race). Proves
# the seam catches a too-fast Enter rather than merely asserting a constant.
reset_state continue pi
write_tape "$IDLE"
export FLEET_DOORBELL_SUBMIT_DELAY_SEC=0.05
run_doorbell aa990009
unset FLEET_DOORBELL_SUBMIT_DELAY_SEC
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa990009 \
   && sent_has 'HAND WAKE hand-1' \
   && ordering_ok "$SENT" \
   && [[ "$(verdict_last)" == *verdict=UNSETTLED* ]]; then
  ok "pi too-fast Enter (0.05s) left composer UNSETTLED (race reproduced); paste→Enter ordering held"
else
  notok "pi too-fast: code=$RUN_CODE verdict=$(verdict_last) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 10: pi send_line default (0.8s) settles and submits ─────────
# The selected Pi default clears the paste-settling window: Enter lands after
# settling, the composer is SETTLED, and the pointer is submitted + recorded.
reset_state continue pi
write_tape "$IDLE"
run_doorbell aa100010
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa100010 \
   && sent_has 'HAND WAKE hand-1' \
   && ordering_ok "$SENT" \
   && [[ "$(verdict_last)" == *verdict=SETTLED* ]]; then
  ok "pi default (0.8s) settled composer; pointer submitted+recorded; paste→Enter ordering held"
else
  notok "pi default: code=$RUN_CODE verdict=$(verdict_last) err=$(cat "$RUN_ERR")"
fi

echo "---"
echo "pass=$pass fail=$fail"
[[ "$fail" -eq 0 ]]
