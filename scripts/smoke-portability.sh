#!/usr/bin/env bash
# smoke-portability.sh — quick env + helper checks (macOS/Linux, bash 3.2+, py 3.9+).
#
# Usage:
#   scripts/smoke-portability.sh [--project <fleet-root>]
#
# Exit: 0 ok · 1 soft fail · 2 hard env fail
set -euo pipefail

_FLEET_SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
# shellcheck source=lib/env.sh
. "$_FLEET_SCRIPT_DIR/lib/env.sh"
fleet_bootstrap_env

PROJECT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project|-p) PROJECT="$2"; shift 2 ;;
    -h|--help)
      fleet_usage_from_header "$0" 2 10
      exit 0
      ;;
    *) echo "unknown: $1" >&2; exit 2 ;;
  esac
done

SOFT=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*"; SOFT=1; }
hard() { printf 'HARD  %s\n' "$*"; exit 2; }

pass "bash $BASH_VERSION (need 3.2+)"
[[ -n "${BASH_VERSION:-}" ]] || hard "not running under bash"

if PYTHON_BIN="$(fleet_find_python3)"; then
  pass "python3: $PYTHON_BIN ($("$PYTHON_BIN" -c 'import sys; print("%d.%d.%d"%sys.version_info[:3])'))"
else
  hard "python3 >= 3.9 not found"
fi

if TMUX_BIN="$(fleet_find_tmux)"; then
  pass "tmux: $TMUX_BIN ($("$TMUX_BIN" -V 2>/dev/null || true))"
else
  fail "tmux not found (sensors/doorbell degraded)"
fi

if VIVI_BIN="$(fleet_find_vivi)"; then
  pass "vivi: $VIVI_BIN"
else
  fail "vivi not found (board sensors degraded)"
fi

pass "date iso: $(fleet_date_iso) epoch: $(fleet_date_epoch)"

# Python modules compile
for py in fleet_common.py fleet-sensors.py fleet-baseline.py verify-fleet-json.py suggest-polish-files.py; do
  if "$PYTHON_BIN" -m py_compile "$_FLEET_SCRIPT_DIR/$py"; then
    pass "py_compile $py"
  else
    hard "py_compile failed: $py"
  fi
done

# Bash syntax
for sh in fleet-doorbell.sh steward.sh codex-reinit.sh opencode-hand-ctl.sh smoke-portability.sh lib/env.sh; do
  if bash -n "$_FLEET_SCRIPT_DIR/$sh"; then
    pass "bash -n $sh"
  else
    hard "bash -n failed: $sh"
  fi
done

# Also accept macOS stock bash 3.2 for syntax of doorbel/env
if [[ -x /bin/bash ]]; then
  if /bin/bash -n "$_FLEET_SCRIPT_DIR/fleet-doorbell.sh" \
    && /bin/bash -n "$_FLEET_SCRIPT_DIR/lib/env.sh"; then
    pass "/bin/bash -n doorbell + env.sh (stock macOS bash)"
  else
    fail "/bin/bash -n failed (bash 3.2 syntax issue)"
  fi
fi

# ISO Z parse on this python
"$PYTHON_BIN" - <<'PY' || hard "ISO Z parse failed"
from datetime import datetime, timezone
s = "2026-07-11T12:00:00Z"
if s.endswith("Z"):
    s = s[:-1] + "+00:00"
dt = datetime.fromisoformat(s)
assert dt.tzinfo is not None
print("ok", int(dt.timestamp()))
PY
pass "ISO-8601 Z normalize"

# Optional live project
if [[ -n "$PROJECT" ]]; then
  if ! PROJECT="$(fleet_abs_project "$PROJECT")"; then
    hard "bad --project: $PROJECT"
  fi
  if [[ -f "$PROJECT/.vivi/fleet.json" ]]; then
    if "$PYTHON_BIN" "$_FLEET_SCRIPT_DIR/fleet-sensors.py" --project "$PROJECT" --no-watch --text >/tmp/fleet-smoke-sensors.txt; then
      pass "fleet-sensors --text on $PROJECT"
    else
      # exit 2 partial still useful
      rc=$?
      if [[ $rc -eq 2 ]]; then
        pass "fleet-sensors partial (exit 2) on $PROJECT"
      else
        fail "fleet-sensors failed rc=$rc"
      fi
    fi
    if "$PYTHON_BIN" "$_FLEET_SCRIPT_DIR/fleet-baseline.py" get -p "$PROJECT" >/dev/null; then
      pass "fleet-baseline get"
    else
      fail "fleet-baseline get failed"
    fi
    # doorbell may refuse down panes — exit 1 is expected
    set +e
    "$_FLEET_SCRIPT_DIR/fleet-doorbell.sh" --project "$PROJECT" hand-1 --note smoke >/tmp/fleet-smoke-door.txt 2>/tmp/fleet-smoke-door.err
    drc=$?
    set -e
    if [[ $drc -eq 0 || $drc -eq 1 ]]; then
      pass "fleet-doorbell ran (rc=$drc; 1=refused ok)"
    else
      fail "fleet-doorbell unexpected rc=$drc"
    fi
  else
    fail "no fleet.json under $PROJECT"
  fi
else
  pass "skip live fleet (pass --project to exercise sensors/baseline/doorbell)"
fi

if [[ $SOFT -ne 0 ]]; then
  echo "DONE with soft failures"
  exit 1
fi
echo "DONE ok"
exit 0
