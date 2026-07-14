#!/usr/bin/env python3
"""Small dependency-free MCP bridge for the canonical Fleet scripts.

The bridge deliberately owns no Fleet policy. It validates inputs, calls the
existing helpers, and returns observations or explicit operations as MCP tool
results. The installed Fleet skill remains the policy source of truth.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any


SERVER_NAME = "fleet"
SERVER_VERSION = "0.1.0"
MIN_LOOP_INTERVAL = 60


def log(message: str) -> None:
    print(f"fleet-mcp: {message}", file=sys.stderr, flush=True)


def jsonrpc(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def tool_result(text: str, structured: Any) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured,
    }


def tool_error(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": message}],
        "isError": True,
    }


def skill_root() -> Path:
    configured = os.environ.get("FLEET_SKILL_ROOT")
    candidates = [Path(configured)] if configured else []
    candidates.extend(
        [
            Path(__file__).resolve().parents[3],
            Path(__file__).resolve().parents[4],
            Path.home() / ".codex" / "skills" / "fleet",
            Path.home() / ".agents" / "skills" / "fleet",
        ]
    )
    for candidate in candidates:
        if (candidate / "scripts" / "fleet-sensors.py").is_file():
            return candidate.resolve()
    raise RuntimeError(
        "Fleet helper scripts were not found; set FLEET_SKILL_ROOT to the "
        "canonical Fleet skill directory"
    )


def script(name: str) -> Path:
    path = skill_root() / "scripts" / name
    if not path.is_file():
        raise RuntimeError(f"Fleet helper is missing: {path}")
    return path


def require_object(arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be an object")
    return arguments


def require_root(arguments: dict[str, Any]) -> Path:
    raw = arguments.get("root")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("root is required")
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Fleet project root does not exist: {root}")
    if not (root / ".vivi" / "fleet.json").is_file():
        raise ValueError(f"no .vivi/fleet.json at Fleet project root: {root}")
    return root


def optional_fleet(arguments: dict[str, Any]) -> str | None:
    value = arguments.get("fleet_id")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("fleet_id must be a non-empty string when supplied")
    return value.strip()


def fleet_args(arguments: dict[str, Any], root: Path) -> list[str]:
    args = ["--project", str(root)]
    fleet_id = optional_fleet(arguments)
    if fleet_id:
        args.extend(["--fleet", fleet_id])
    return args


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 45,
    accepted_codes: set[int] | None = None,
) -> tuple[int, str, str]:
    accepted = accepted_codes or {0}
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"command not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"command timed out after {timeout:g}s: {command[0]}") from exc
    if completed.returncode not in accepted:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"{command[0]} exited {completed.returncode}"
            + (f": {detail[:600]}" if detail else "")
        )
    return completed.returncode, completed.stdout, completed.stderr


def parse_json_output(stdout: str, label: str) -> Any:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} returned invalid JSON: {exc}") from exc


def helper_json(
    name: str,
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 45,
    accepted_codes: set[int] | None = None,
) -> Any:
    _, stdout, _ = run_command(
        ["python3", str(script(name)), *args],
        cwd=cwd,
        timeout=timeout,
        accepted_codes=accepted_codes,
    )
    return parse_json_output(stdout, name)


def verify(arguments: dict[str, Any], root: Path) -> Any:
    return helper_json(
        "verify-fleet-json.py",
        [*fleet_args(arguments, root), "--json"],
        timeout=30,
    )


def sensors(arguments: dict[str, Any], root: Path) -> Any:
    return helper_json(
        "fleet-sensors.py",
        [*fleet_args(arguments, root), "--json", "--no-watch"],
        timeout=45,
        accepted_codes={0, 2},
    )


def baseline(arguments: dict[str, Any], root: Path) -> Any:
    return helper_json(
        "fleet-baseline.py",
        ["get", *fleet_args(arguments, root)],
        timeout=20,
    )


def posture(arguments: dict[str, Any], root: Path, action: str) -> Any:
    args = [*fleet_args(arguments, root), "--json", action]
    if action == "set":
        mode = arguments.get("mode")
        if mode not in {"growth", "standby", "dormant"}:
            raise ValueError("mode must be growth, standby, or dormant")
        args.append(mode)
        reason = arguments.get("reason")
        if reason:
            args.extend(["--reason", str(reason)])
        for trigger in arguments.get("wake_triggers", []) or []:
            if not isinstance(trigger, str) or not trigger.strip():
                raise ValueError("wake_triggers must contain non-empty strings")
            args.extend(["--wake-trigger", trigger])
    return helper_json("fleet-posture.py", args, timeout=20)


def loop(arguments: dict[str, Any], root: Path) -> Any:
    action = arguments.get("action", "status")
    if action not in {"status", "start", "stop"}:
        raise ValueError("action must be status, start, or stop")
    args = [*fleet_args(arguments, root), action]
    if action == "start":
        interval = arguments.get("interval", "5m")
        if not isinstance(interval, str) or not interval.strip():
            raise ValueError("interval must be a duration such as 5m")
        target = arguments.get("target")
        if not isinstance(target, str) or not target.strip():
            raise ValueError("target is required when starting a tmux Fleet loop")
        args.extend([interval, "--target", target])
        if arguments.get("immediate") is True:
            args.append("--immediate")
    if action == "stop" and arguments.get("clear_stale") is True:
        args.append("--clear-stale")
    return helper_json("fleet-loop.py", args, timeout=20)


def runtime(arguments: dict[str, Any], root: Path) -> Any:
    action = arguments.get("action", "status")
    if action not in {"status", "start", "stop", "restart", "reinit", "doctor"}:
        raise ValueError("action must be status, start, stop, restart, reinit, or doctor")
    args = [*fleet_args(arguments, root), "--json", action]
    roles = arguments.get("roles", []) or []
    if not isinstance(roles, list) or not all(isinstance(role, str) and role.strip() for role in roles):
        raise ValueError("roles must be a list of role names")
    for role in roles:
        args.extend(["--role", role])
    if not roles and action in {"status", "doctor"}:
        args.extend(["--hands", "all", "--heads", "all"])
    if arguments.get("force") is True:
        args.append("--force")
    boot = arguments.get("boot")
    if boot:
        args.extend(["--boot", str(boot)])
    return helper_json("fleet-runtime.py", args, timeout=45)


def cycle_close(arguments: dict[str, Any], root: Path) -> Any:
    disposition = arguments.get("disposition")
    if disposition not in {"acted", "quiet"}:
        raise ValueError("disposition must be acted or quiet")
    summary = arguments.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summary is required")
    args = [*fleet_args(arguments, root), f"--{disposition}", "--summary", summary, "--no-watch"]
    if arguments.get("operator_engaged") is True:
        args.append("--operator-engaged")
    if arguments.get("detach") is True:
        args.append("--detach")
    return helper_json("fleet-cycle-close.py", args, timeout=45)


def fleet_identity(root: Path, arguments: dict[str, Any]) -> dict[str, Any]:
    snapshot = json.loads((root / ".vivi" / "fleet.json").read_text(encoding="utf-8"))
    fleet_id = optional_fleet(arguments)
    if fleet_id is None:
        for key in ("fleet_id", "mailspace"):
            if isinstance(snapshot.get(key), str) and snapshot[key].strip():
                fleet_id = snapshot[key].strip()
                break
    return {"root": str(root), "fleet_id": fleet_id}


def attach(arguments: dict[str, Any], root: Path, attached: dict[str, dict[str, Any]]) -> Any:
    mode = arguments.get("mode", "mind")
    if mode not in {"mind", "monitor"}:
        raise ValueError("mode must be mind or monitor")
    verification = verify(arguments, root)
    identity = fleet_identity(root, arguments)
    key = str(root)
    if mode == "monitor":
        attached[key] = {**identity, "mode": "monitor"}
        return {"attachment": attached[key], "verification": verification, "read_only": True}

    current = baseline(arguments, root)
    owner = current.get("mind_session") if isinstance(current, dict) else None
    owner_label = owner.get("label") if isinstance(owner, dict) else None
    label = f"codex:{socket.gethostname()}:{os.getpid()}"
    takeover = arguments.get("takeover") is True
    if owner_label and owner_label != label and not takeover:
        raise ValueError(
            f"{identity['fleet_id']} is attached to another Mind session ({owner_label}); "
            "retry with takeover=true only after confirming it is dead or yielded"
        )
    summary = f"codex fleet {'takeover' if takeover else 'attach'}: {label}"
    bump_args = [
        "bump",
        *fleet_args(arguments, root),
        "--summary",
        summary,
        "--acted",
        "--mind-session",
        label,
        "--mind-host",
        socket.gethostname(),
        "--recap",
        f"{'Took over' if takeover else 'Attached'} Mind session {label}",
    ]
    updated = helper_json("fleet-baseline.py", bump_args, timeout=25)
    attached[key] = {**identity, "mode": "mind", "label": label}
    return {"attachment": attached[key], "baseline": updated, "verification": verification}


def detach(arguments: dict[str, Any], root: Path, attached: dict[str, dict[str, Any]]) -> Any:
    key = str(root)
    current = baseline(arguments, root)
    owner = current.get("mind_session") if isinstance(current, dict) else None
    owner_label = owner.get("label") if isinstance(owner, dict) else None
    attachment = attached.get(key)
    if attachment and attachment.get("mode") == "mind" and owner_label not in {None, attachment.get("label")}:
        raise ValueError(f"{attachment.get('fleet_id')} is attached to another Mind session ({owner_label})")
    if attachment and attachment.get("mode") == "mind":
        updated = helper_json(
            "fleet-baseline.py",
            ["bump", *fleet_args(arguments, root), "--summary", "codex fleet detach", "--acted", "--detach"],
            timeout=25,
        )
    else:
        updated = current
    attached.pop(key, None)
    return {"detached": fleet_identity(root, arguments), "baseline": updated}


def board(root: Path) -> Any:
    _, stdout, _ = run_command(
        ["vivi", "--project", str(root), "board", "--json"],
        cwd=root,
        timeout=30,
    )
    return parse_json_output(stdout, "vivi board")


def role_state(row: Any) -> str:
    if not isinstance(row, dict):
        return "unknown"
    runtime_value = row.get("runtime")
    if isinstance(runtime_value, dict):
        for key in ("state", "process_state"):
            if isinstance(runtime_value.get(key), str) and runtime_value[key] != "unknown":
                return runtime_value[key]
    return str(row.get("state", "unknown"))


def snapshot_counts(snapshot: Any) -> dict[str, int]:
    if not isinstance(snapshot, dict):
        return {"actionable": 0, "mail": 0, "needs": 0, "rtm": 0}
    actionable = 0
    mail = 0
    needs = 0
    mind = snapshot.get("mind")
    operator = snapshot.get("operator")
    if isinstance(mind, dict):
        mail += int(mind.get("inbox_unread", 0) or 0)
    if isinstance(operator, dict):
        needs += int(operator.get("open_count", 0) or 0)
    for group_name in ("hands", "heads"):
        group = snapshot.get(group_name)
        if not isinstance(group, dict):
            continue
        for row in group.values():
            if not isinstance(row, dict):
                continue
            actionable += int(row.get("actionable", 0) or 0)
            mail += int(row.get("inbox_unread", 0) or 0)
            needs += int(row.get("needs_open", 0) or 0)
    integration = snapshot.get("integration")
    rtm = int(integration.get("pending_rtm_count", 0) or 0) if isinstance(integration, dict) else 0
    return {"actionable": actionable, "mail": mail, "needs": needs, "rtm": rtm}


def safe_runtime(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        key: value[key]
        for key in ("kind", "target", "state", "process_state", "confidence", "evidence")
        if key in value
    }


def safe_role(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result = {
        key: value[key]
        for key in (
            "mail_identity",
            "actionable",
            "tasks_open",
            "needs_open",
            "sweep_enabled",
            "sweep_due",
            "state",
        )
        if key in value
    }
    runtime_value = safe_runtime(value.get("runtime"))
    if runtime_value is not None:
        result["runtime"] = runtime_value
    return result


def safe_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {
        key: value[key]
        for key in (
            "ok",
            "at",
            "project",
            "fleet_id",
            "fleet_json",
            "focus",
            "identities",
            "signals",
            "fingerprint",
            "partial",
        )
        if key in value
    }
    result["hands"] = {name: safe_role(row) for name, row in (value.get("hands") or {}).items()}
    result["heads"] = {name: safe_role(row) for name, row in (value.get("heads") or {}).items()}
    for group_name in ("operator", "mind", "integration"):
        group = value.get(group_name)
        if isinstance(group, dict):
            result[group_name] = {
                key: group[key]
                for key in (
                    "identity",
                    "inbox_unread",
                    "needs_open",
                    "open_count",
                    "to_mind_count",
                    "pending_rtm_count",
                    "merged_rtm_count",
                    "unresolved_rtm_count",
                )
                if key in group
            }
    posture_value = value.get("fleet_posture")
    if isinstance(posture_value, dict):
        result["fleet_posture"] = {
            key: posture_value[key]
            for key in ("mode", "reason", "since", "wake_triggers")
            if key in posture_value
        }
    steward = value.get("steward")
    if isinstance(steward, dict):
        result["steward"] = {
            key: steward[key]
            for key in ("enabled", "armed", "tripped", "last_successful_cycle_at", "last_rearm_at")
            if key in steward
        }
    git = value.get("git")
    if isinstance(git, dict):
        result["git"] = git
    return result


def dashboard(preflight: dict[str, Any]) -> str:
    snapshot = preflight.get("snapshot") or {}
    baseline_value = preflight.get("baseline") or {}
    fleet = preflight.get("fleet") or {}
    posture_value = (snapshot.get("fleet_posture") or {}).get("mode", "unknown")
    hands = snapshot.get("hands") or {}
    heads = snapshot.get("heads") or {}
    active_hands = sum(role_state(row) in {"starting", "submitting", "running"} for row in hands.values())
    active_heads = sum(role_state(row) in {"starting", "submitting", "running"} for row in heads.values())
    counts = snapshot_counts(snapshot)
    signals = snapshot.get("signals") or []
    summary = baseline_value.get("last_cycle_summary", "cycle observed")
    return "\n".join(
        [
            f"◈ {fleet.get('fleet_id', 'fleet')} {preflight.get('mode', 'unattached')} {posture_value} · cycle {baseline_value.get('last_cycle', '—')}",
            f"  Hand {active_hands}/{len(hands)} · Head {active_heads}/{len(heads)}",
            f"  Vivi · work {counts['actionable']} · ✉{counts['mail']} · ⚑{counts['needs']} · ↻{counts['rtm']} · !{len(signals)}",
            f"  last: {summary}",
        ]
    )


def preflight(arguments: dict[str, Any], root: Path, attached: dict[str, dict[str, Any]]) -> dict[str, Any]:
    identity = fleet_identity(root, arguments)
    snapshot = safe_snapshot(sensors(arguments, root))
    current_baseline = baseline(arguments, root)
    external_loop = helper_json(
        "fleet-loop.py",
        [*fleet_args(arguments, root), "status"],
        timeout=20,
    )
    current_posture = posture(arguments, root, "get")
    runtime_state = runtime({**arguments, "action": "status"}, root)
    mode = (attached.get(str(root)) or {}).get("mode", "unattached")
    signals = snapshot.get("signals") if isinstance(snapshot, dict) else []
    recommendations: list[str] = []
    if signals:
        recommendations.append("inspect and disposition every sensor signal")
    if isinstance(current_posture, dict) and current_posture.get("mode") == "growth":
        recommendations.append("preserve growth-liveness refill behavior")
    if not signals:
        recommendations.append("no material sensor signals")
    return {
        "fleet": identity,
        "mode": mode,
        "snapshot": snapshot,
        "baseline": current_baseline,
        "external_loop": external_loop,
        "posture": current_posture,
        "runtime": runtime_state,
        "recommendations": recommendations,
    }


def tool_definitions() -> list[dict[str, Any]]:
    root = {"type": "string", "description": "Fleet project root containing .vivi/fleet.json"}
    fleet_id = {"type": "string", "description": "Logical fleet ID from fleet.json"}
    return [
        {
            "name": "fleet_attach",
            "description": "Attach a Fleet as Mind or as a read-only monitor. Mind attachment claims the canonical advisory baseline lock.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id, "mode": {"type": "string", "enum": ["mind", "monitor"]}, "takeover": {"type": "boolean"}}, "required": ["root"]},
            "annotations": {"readOnlyHint": False, "destructiveHint": False},
        },
        {
            "name": "fleet_detach",
            "description": "Detach the current Codex Mind or stop a read-only monitor.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id}, "required": ["root"]},
            "annotations": {"readOnlyHint": False, "destructiveHint": False},
        },
        {
            "name": "fleet_preflight",
            "description": "Run a read-only Fleet preflight covering sensors, baseline, posture, runtime, loop state, and recommendations.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id}, "required": ["root"]},
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        },
        {
            "name": "fleet_sensors",
            "description": "Read a no-watch canonical Fleet sensor snapshot.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id}, "required": ["root"]},
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        },
        {
            "name": "fleet_board",
            "description": "Read the project-local Vivi board as JSON.",
            "inputSchema": {"type": "object", "properties": {"root": root}, "required": ["root"]},
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        },
        {
            "name": "fleet_runtime",
            "description": "Inspect configured Fleet process and pane runtime state.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id}, "required": ["root"]},
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        },
        {
            "name": "fleet_dashboard",
            "description": "Render a compact Codex conversation dashboard from canonical Fleet observations.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id}, "required": ["root"]},
            "annotations": {"readOnlyHint": True, "destructiveHint": False},
        },
        {
            "name": "fleet_loop",
            "description": "Inspect or control the tmux-backed Fleet cycle loop. Starting requires an explicit tmux target.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id, "action": {"type": "string", "enum": ["status", "start", "stop"]}, "interval": {"type": "string"}, "target": {"type": "string"}, "immediate": {"type": "boolean"}, "clear_stale": {"type": "boolean"}}, "required": ["root"]},
            "annotations": {"readOnlyHint": False, "destructiveHint": False},
        },
        {
            "name": "fleet_posture",
            "description": "Read or atomically change Fleet posture.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id, "action": {"type": "string", "enum": ["get", "set"]}, "mode": {"type": "string", "enum": ["growth", "standby", "dormant"]}, "reason": {"type": "string"}, "wake_triggers": {"type": "array", "items": {"type": "string"}}}, "required": ["root"]},
            "annotations": {"readOnlyHint": False, "destructiveHint": False},
        },
        {
            "name": "fleet_runtime_action",
            "description": "Run a canonical Fleet runtime lifecycle action for explicitly named roles.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id, "action": {"type": "string", "enum": ["status", "start", "stop", "restart", "reinit", "doctor"]}, "roles": {"type": "array", "items": {"type": "string"}}, "force": {"type": "boolean"}, "boot": {"type": "string"}}, "required": ["root"]},
            "annotations": {"readOnlyHint": False, "destructiveHint": True},
        },
        {
            "name": "fleet_cycle_close",
            "description": "Close a Mind cycle through the canonical sensors and baseline helper.",
            "inputSchema": {"type": "object", "properties": {"root": root, "fleet_id": fleet_id, "disposition": {"type": "string", "enum": ["acted", "quiet"]}, "summary": {"type": "string"}, "operator_engaged": {"type": "boolean"}, "detach": {"type": "boolean"}}, "required": ["root", "disposition", "summary"]},
            "annotations": {"readOnlyHint": False, "destructiveHint": False},
        },
    ]


def dispatch(name: str, arguments: Any, attached: dict[str, dict[str, Any]]) -> dict[str, Any]:
    params = require_object(arguments)
    root = require_root(params)
    if name == "fleet_attach":
        result = attach(params, root, attached)
        return tool_result(f"Attached {result['attachment']['fleet_id']} ({result['attachment']['mode']})", result)
    if name == "fleet_detach":
        result = detach(params, root, attached)
        return tool_result(f"Detached {result['detached']['fleet_id']}", result)
    if name == "fleet_preflight":
        result = preflight(params, root, attached)
        return tool_result(dashboard(result) + "\n  recommendations: " + "; ".join(result["recommendations"]), result)
    if name == "fleet_sensors":
        result = {"fleet": fleet_identity(root, params), "snapshot": safe_snapshot(sensors(params, root))}
        return tool_result(json.dumps(result, indent=2), result)
    if name == "fleet_board":
        result = {"fleet": fleet_identity(root, params), "board": board(root)}
        return tool_result(json.dumps(result, indent=2), result)
    if name == "fleet_runtime":
        result = {"fleet": fleet_identity(root, params), "runtime": runtime({**params, "action": "status"}, root)}
        return tool_result(json.dumps(result, indent=2), result)
    if name == "fleet_dashboard":
        result = preflight(params, root, attached)
        return tool_result(dashboard(result), {"kind": "fleet-dashboard", **result})
    if name == "fleet_loop":
        result = {"fleet": fleet_identity(root, params), "loop": loop(params, root)}
        return tool_result(json.dumps(result, indent=2), result)
    if name == "fleet_posture":
        result = {"fleet": fleet_identity(root, params), "posture": posture(params, root, params.get("action", "get"))}
        return tool_result(json.dumps(result, indent=2), result)
    if name == "fleet_runtime_action":
        result = {"fleet": fleet_identity(root, params), "runtime": runtime(params, root)}
        return tool_result(json.dumps(result, indent=2), result)
    if name == "fleet_cycle_close":
        result = {"fleet": fleet_identity(root, params), "cycle": cycle_close(params, root)}
        return tool_result(json.dumps(result, indent=2), result)
    raise ValueError(f"unknown tool: {name}")


def handle(request: dict[str, Any], attached: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    method = request.get("method")
    request_id = request.get("id")
    if method == "initialize":
        requested = (request.get("params") or {}).get("protocolVersion", "2024-11-05")
        return jsonrpc(
            request_id,
            {
                "protocolVersion": requested,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "ping":
        return jsonrpc(request_id, {})
    if method == "tools/list":
        return jsonrpc(request_id, {"tools": tool_definitions()})
    if method == "tools/call":
        params = request.get("params") or {}
        try:
            result = dispatch(params.get("name", ""), params.get("arguments", {}), attached)
        except (RuntimeError, ValueError, OSError) as exc:
            log(str(exc))
            result = tool_error(str(exc))
        return jsonrpc(request_id, result)
    if request_id is None:
        return None
    return jsonrpc_error(request_id, -32601, f"method not found: {method}")


def main() -> int:
    attached: dict[str, dict[str, Any]] = {}
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("JSON-RPC request must be an object")
            response = handle(request, attached)
            if response is not None:
                print(json.dumps(response, separators=(",", ":")), flush=True)
        except (json.JSONDecodeError, ValueError) as exc:
            log(f"invalid request: {exc}")
            print(json.dumps(jsonrpc_error(None, -32600, str(exc))), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
