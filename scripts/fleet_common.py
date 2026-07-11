"""Shared portability helpers for fleet Python scripts.

Target: Python 3.9+ on macOS and Linux. No third-party deps.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

MIN_PY: Tuple[int, int] = (3, 9)
PathLike = Union[str, Path]


def require_python(min_version: Tuple[int, int] = MIN_PY) -> None:
    """Exit 2 if the interpreter is too old."""
    if sys.version_info < min_version:
        need = "%d.%d" % (min_version[0], min_version[1])
        have = "%d.%d.%d" % sys.version_info[:3]
        sys.stderr.write(
            "fleet: python >= %s required (running %s via %s)\n"
            % (need, have, sys.executable)
        )
        sys.exit(2)


def now_iso() -> str:
    """UTC timestamp as YYYY-MM-DDTHH:MM:SSZ (no microseconds)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_to_epoch(value: Optional[str]) -> int:
    """Parse ISO-8601 (with or without trailing Z) to unix epoch seconds.

    Python < 3.11 rejects trailing Z on fromisoformat; always normalize.
    Returns 0 on empty/unparseable input.
    """
    if not value:
        return 0
    s = str(value).strip()
    if not s:
        return 0
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def read_text(path: PathLike) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text_atomic(path: PathLike, text: str) -> None:
    """Write text atomically (temp file in same dir + os.replace)."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".%s." % dest.name,
        suffix=".tmp",
        dir=str(dest.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, dest)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_json(path: PathLike, default: Optional[Any] = None) -> Any:
    """Load JSON from path; missing/invalid file returns default (or {})."""
    fallback = {} if default is None else default
    p = Path(path)
    if not p.is_file():
        return fallback
    try:
        return json.loads(read_text(p))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return fallback


def save_json(path: PathLike, data: Any) -> None:
    write_text_atomic(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def which(
    name: str,
    tooling: Optional[Dict[str, Any]] = None,
    key: Optional[str] = None,
) -> Optional[str]:
    """Resolve a binary: optional fleet tooling override, then PATH."""
    if tooling and key:
        block = tooling.get(key) or {}
        if isinstance(block, dict):
            binary = block.get("binary")
            if binary and Path(binary).is_file() and os.access(binary, os.X_OK):
                return str(binary)
    return shutil.which(name)


def run_cmd(
    cmd: Sequence[str],
    timeout: float = 30.0,
    cwd: Optional[PathLike] = None,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str]:
    """Run a command; return (rc, combined utf-8 text). Never raises for rc != 0."""
    try:
        proc = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd else None,
            env=env,
        )
        out = proc.stdout or ""
        if proc.stderr and proc.returncode:
            if out and not out.endswith("\n"):
                out += "\n"
            out += proc.stderr
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "timeout: %s" % " ".join(cmd)
    except FileNotFoundError:
        return 127, "missing: %s" % (cmd[0] if cmd else "?")
    except OSError as exc:
        return 126, "os error: %s" % exc


def ensure_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []
