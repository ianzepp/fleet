# fleet/scripts/lib/env.sh — portable bash bootstrap for fleet shell helpers.
#
# Source from any fleet bash script:
#   _FLEET_SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
#   # shellcheck source=lib/env.sh
#   . "$_FLEET_SCRIPT_DIR/lib/env.sh"
#   fleet_bootstrap_env
#
# Contract:
#   - Requires bash (3.2+ macOS /bin/bash, or bash 4/5). Not sh, not zsh-as-script.
#   - Safe on Linux and macOS. Does not assume Homebrew, GNU coreutils, or a login PATH.
#   - Callers may still override TMUX_BIN / PYTHON_BIN / VIVI_BIN / etc.
#
# shellcheck shell=bash

# Guard double-source
if [[ -n "${_FLEET_ENV_SH_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
_FLEET_ENV_SH_LOADED=1

fleet_require_bash() {
  if [[ -z "${BASH_VERSION:-}" ]]; then
    printf '%s\n' "ERROR: fleet scripts must run under bash (not sh/zsh)." >&2
    printf '%s\n' "  Use: bash \"$0\" …   or ensure the shebang is #!/usr/bin/env bash" >&2
    exit 2
  fi
}

# Prepend common tool dirs without clobbering an already-good PATH.
# Order: keep caller PATH first, then fill gaps with system + user + optional brew.
fleet_bootstrap_path() {
  local d extras
  extras=""
  # shellcheck disable=SC2088
  for d in \
    /usr/bin \
    /bin \
    /usr/sbin \
    /sbin \
    "${HOME}/.cargo/bin" \
    "${HOME}/.local/bin" \
    /opt/homebrew/bin \
    /usr/local/bin \
    /home/linuxbrew/.linuxbrew/bin
  do
    [[ -n "$d" && -d "$d" ]] || continue
    case ":${PATH:-}:" in
      *":$d:"*) ;;
      *) extras="${extras:+$extras:}$d" ;;
    esac
  done
  if [[ -n "$extras" ]]; then
    PATH="${PATH:+$PATH:}$extras"
  fi
  export PATH
}

fleet_bootstrap_env() {
  fleet_require_bash
  fleet_bootstrap_path
  # Prefer C.UTF-8 / UTF-8 for JSON and pane captures; fall back quietly.
  if [[ -z "${LC_ALL:-}" && -z "${LC_CTYPE:-}" ]]; then
    if locale -a 2>/dev/null | grep -Eqi '^(C\.UTF-8|en_US\.UTF-8|UTF-8)$'; then
      export LC_CTYPE="${LC_CTYPE:-C.UTF-8}"
    fi
  fi
}

# Print first executable among candidates (absolute paths or bare names on PATH).
fleet_find_bin() {
  local c
  for c in "$@"; do
    [[ -n "$c" ]] || continue
    if [[ "$c" == */* ]]; then
      [[ -x "$c" ]] && { printf '%s\n' "$c"; return 0; }
    else
      if command -v "$c" >/dev/null 2>&1; then
        command -v "$c"
        return 0
      fi
    fi
  done
  return 1
}

# Resolve python3 >= 3.9. Honors PYTHON_BIN if set and valid.
fleet_find_python3() {
  local c ver
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    if [[ -x "$PYTHON_BIN" ]] && "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      printf '%s\n' "$PYTHON_BIN"
      return 0
    fi
  fi
  for c in \
    "$(command -v python3 2>/dev/null || true)" \
    /usr/bin/python3 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3 \
    "${HOME}/.local/bin/python3" \
    /home/linuxbrew/.linuxbrew/bin/python3 \
    python3
  do
    [[ -n "$c" ]] || continue
    if [[ "$c" == */* ]]; then
      [[ -x "$c" ]] || continue
    else
      command -v "$c" >/dev/null 2>&1 || continue
      c="$(command -v "$c")"
    fi
    if "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  return 1
}

fleet_find_tmux() {
  if [[ -n "${TMUX_BIN:-}" && -x "${TMUX_BIN}" ]]; then
    printf '%s\n' "$TMUX_BIN"
    return 0
  fi
  fleet_find_bin tmux /opt/homebrew/bin/tmux /usr/local/bin/tmux /usr/bin/tmux || return 1
}

fleet_find_vivi() {
  if [[ -n "${VIVI_BIN:-}" && -x "${VIVI_BIN}" ]]; then
    printf '%s\n' "$VIVI_BIN"
    return 0
  fi
  fleet_find_bin vivi \
    "${HOME}/.cargo/bin/vivi" \
    /opt/homebrew/bin/vivi \
    /usr/local/bin/vivi \
    "${HOME}/.local/bin/vivi" || return 1
}

# Portable usage printer: strip leading "# " or "#" from header comment lines.
fleet_usage_from_header() {
  local file="$1"
  local start="${2:-2}"
  local end="${3:-20}"
  sed -n "${start},${end}p" "$file" | sed -e 's/^# //' -e 's/^#//'
}

# ISO-8601 UTC timestamp (works with BSD and GNU date).
fleet_date_iso() {
  date -u +%Y-%m-%dT%H:%M:%SZ
}

# Unix epoch seconds UTC.
fleet_date_epoch() {
  date -u +%s
}

# Resolve a project path to absolute (fail if missing).
fleet_abs_project() {
  local p="$1"
  if [[ -z "$p" ]]; then
    return 1
  fi
  if [[ ! -d "$p" ]]; then
    return 1
  fi
  (CDPATH= cd -- "$p" && pwd)
}

# Safe shift-2 for option parsers under set -u.
fleet_need_optarg() {
  local opt="$1"
  local val="${2-}"
  if [[ -z "${val}" || "$val" == --* ]]; then
    printf '%s\n' "ERROR: $opt requires a value" >&2
    return 2
  fi
  return 0
}
