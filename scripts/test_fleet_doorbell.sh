#!/usr/bin/env bash
# Focused tests for scripts/fleet-doorbell.sh — Pi /new pointer-loss race.
#
# Covers the transition-aware preparation + pointer acknowledgement fix:
#   1. stale-idle immediate classifier race       => refuse, no wake record
#   2. delayed /new transition                     => success, wake recorded
#   3. successful fresh readiness                  => success, wake recorded
#   4. pointer never acknowledged (new)            => refuse, no wake record
#   5. continue + new handle, no --no-prepare      => success, no forced ack (P1)
#   6. pointer never acknowledged (compact)        => refuse, no wake record
#
# Scenario 5 is the continue-mode P1 regression: a new handle under
# assignment_mode=continue must skip preparation, so DID_PREPARE stays 0 and a
# general Pi pointer needs no acknowledgement (historical pointer-only behavior).
# Scenario 6 proves the prepared-ack gate still holds for compact (DID_PREPARE=1).
#
# Injection: the script zeros TMUX_BIN at startup, so we place a fake `tmux`
# on PATH (found via `command -v tmux`); PYTHON_BIN is honored from env.
# The fake tmux serves scripted pane snapshots from a tape file (one per
# capture-pane call; repeats the last line when exhausted) and records every
# send-keys call to a log.
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

# Pi pane snapshots (single-line; classify_tmux_text matches on the whole text).
IDLE='pi v0.80 (zai) glm-5.2 low 0.0%/1.0M (auto)'
RUNNING='Thinking… handling HAND WAKE'
NEW_DONE='New session started'   # differs from IDLE -> transition marker
COMPACT_DONE='Compacted session' # differs from IDLE -> transition marker

# fleet.json writer: pi hand role with a configurable assignment_mode.
# Scenarios 1-4 use `new`; scenario 5 uses `continue` (the P1 path); scenario 6
# uses `compact`. Unquoted heredoc so $mode expands.
write_fleet_config() {
  local mode="$1"
  cat > "$TMP/project/.vivi/fleet.json" <<JSON
{
  "fleet_id": "test",
  "hands": {
    "hand-1": {
      "tmux_target": "test:hand-1.1",
      "agent": "pi",
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
    exit 0
    ;;
  *) exit 0 ;;
esac
SH
chmod +x "$FAKEBIN/tmux"

pass=0
fail=0
ok()   { echo "ok   - $1"; pass=$((pass+1)); }
notok(){ echo "FAIL - $1"; fail=$((fail+1)); }

# Reset per-scenario state, write a fresh tape, and run the doorbell.
# Args: handle, extra doorbell args... ; tape is read from $TAPE before call.
# Sets RUN_CODE, RUN_OUT, RUN_ERR.
reset_state() {
  rm -f "$BASELINE" "$SENT" "$CURSOR"
  : > "$SENT"
  echo "0" > "$CURSOR"
  write_fleet_config "${1:-new}"
}
write_tape() { : > "$TAPE"; local ln; for ln in "$@"; do printf '%s\n' "$ln" >> "$TAPE"; done; }

run_doorbell() {
  local handle="$1"; shift
  RUN_ERR="$TMP/err.log"
  set +e
  RUN_OUT="$(env PATH="$FAKEBIN:$PATH" \
    PYTHON_BIN="$PYTHON_BIN" \
    TAPE_FILE="$TAPE" CURSOR_FILE="$CURSOR" SENT_FILE="$SENT" \
    FLEET_DOORBELL_PREPARE_TIMEOUT_SEC=3 \
    FLEET_DOORBELL_TRANSITION_TIMEOUT_SEC=1 \
    FLEET_DOORBELL_SUBMIT_ACK_TIMEOUT_SEC=2 \
    bash "$DOORBELL" --project "$TMP/project" --role hand-1 --handle "$handle" "$@" 2>"$RUN_ERR")"
  RUN_CODE=$?
  set -e
}

baseline_has_handle() { [[ -f "$BASELINE" ]] && grep -q "$1" "$BASELINE"; }
sent_has() { grep -q -- "$1" "$SENT"; }

# ── Scenario 1: stale-idle immediate classifier race => refuse ───────────
reset_state
write_tape "$IDLE"   # pane never changes after /new (stale idle forever)
run_doorbell aa110001
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa110001 \
   && sent_has '/new' \
   && ! sent_has 'HAND WAKE hand-1'; then
  ok "stale-idle race refused (exit 1), no wake record, /new sent, pointer NOT sent"
else
  notok "stale-idle race: code=$RUN_CODE baseline=$(baseline_has_handle aa110001 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 2: delayed /new transition => success ──────────────────────
reset_state
# 4 idle (init, stopped-check, CLASS, before-sig), 2 stale transition polls,
# then transition marker, fresh idle, main classify idle, pointer running.
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$NEW_DONE" "$IDLE" "$IDLE" "$RUNNING"
run_doorbell aa220002
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa220002 \
   && sent_has '/new' \
   && sent_has 'HAND WAKE hand-1'; then
  ok "delayed /new transition succeeded after stale polls; wake recorded"
else
  notok "delayed transition: code=$RUN_CODE baseline=$(baseline_has_handle aa220002 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 3: successful fresh readiness => success ───────────────────
reset_state
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$NEW_DONE" "$IDLE" "$IDLE" "$RUNNING"
run_doorbell aa330003
if [[ "$RUN_CODE" -eq 0 ]] \
   && baseline_has_handle aa330003 \
   && sent_has 'HAND WAKE hand-1'; then
  ok "fresh readiness succeeded promptly; wake recorded"
else
  notok "fresh readiness: code=$RUN_CODE baseline=$(baseline_has_handle aa330003 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 4: pointer never acknowledged => refuse, no wake record ────
reset_state
# /new transitions + fresh idle OK, but pointer leaves pane idle (never running).
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$NEW_DONE" "$IDLE" "$IDLE"
run_doorbell aa440004
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa440004 \
   && sent_has 'HAND WAKE hand-1'; then
  ok "pointer never acknowledged refused (exit 1), no wake record, pointer was sent"
else
  notok "pointer never ack: code=$RUN_CODE baseline=$(baseline_has_handle aa440004 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

# ── Scenario 5: continue + new handle, no --no-prepare => success (P1) ──────
reset_state continue
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

# ── Scenario 6: pointer never acknowledged (compact) => refuse ──────────
# Gate proof: assignment_mode=compact runs real preparation (DID_PREPARE=1),
# so an unacknowledged pointer must still refuse and record no wake.
reset_state compact
write_tape "$IDLE" "$IDLE" "$IDLE" "$IDLE" "$COMPACT_DONE" "$IDLE" "$IDLE"
run_doorbell aa660006
if [[ "$RUN_CODE" -eq 1 ]] \
   && ! baseline_has_handle aa660006 \
   && sent_has '/compact' \
   && sent_has 'HAND WAKE hand-1'; then
  ok "compact pointer never acknowledged refused (exit 1), no wake record, pointer was sent"
else
  notok "compact never ack: code=$RUN_CODE baseline=$(baseline_has_handle aa660006 && echo y || echo n) err=$(cat "$RUN_ERR")"
fi

echo "---"
echo "pass=$pass fail=$fail"
[[ "$fail" -eq 0 ]]
