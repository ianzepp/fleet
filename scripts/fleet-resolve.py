#!/usr/bin/env python3
"""Resolve one logical fleet role into a backend-neutral runtime binding.

This is a narrow adapter for shell helpers. It is intentionally not a fleet
dispatcher: it only validates scope and emits the binding derived by
``fleet_common.py``.

  fleet-resolve.py --project <root> --role hand-1 [--json]
  fleet-resolve.py --project <root> --list [--agent codex|opencode]
  fleet-resolve.py --project <root> --fleet-file <path> --role head-cto --shell
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    FleetScopeError,
    add_fleet_scope_arguments,
    require_python,
    role_names,
    resolve_fleet_file,
    resolve_runtime_binding,
)

require_python()


def shell_output(binding: dict) -> str:
    """Emit safely quoted scalar/array assignments for bash helpers."""
    lines = []
    scalar_names = (
        "fleet_id", "role", "group", "kind", "mail_identity", "cwd", "target",
        "session", "window", "pane", "socket", "agent", "driver", "model", "launch",
        "min_seconds_between_wakes", "assignment_mode",
    )
    for name in scalar_names:
        lines.append("RESOLVED_%s=%s" % (name.upper(), shlex.quote(str(binding.get(name, "")))))
    command = binding.get("runtime_command")
    if not isinstance(command, list):
        command = []
    lines.append("RESOLVED_RUNTIME_COMMAND=(%s)" % " ".join(shlex.quote(str(item)) for item in command))
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Resolve a logical fleet role")
    add_fleet_scope_arguments(parser, include_role=True)
    parser.add_argument("--runtime-target", default=None, help="explicit backend target override")
    parser.add_argument("--list", action="store_true", help="list configured roles instead of resolving one")
    parser.add_argument("--agent", default=None, help="filter --list by configured agent")
    parser.add_argument("--kind", default=None, help="filter --list by runtime kind")
    parser.add_argument("--group", default=None, help="filter --list by role group (hand or head)")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="emit JSON (default)")
    output.add_argument("--shell", action="store_true", help="emit safely quoted shell assignments")
    args = parser.parse_args(argv)
    if not args.list and (not args.role or len(args.role) != 1):
        parser.error("exactly one --role is required")
    if args.list and args.role:
        parser.error("--role cannot be combined with --list")
    try:
        _, fleet = resolve_fleet_file(args.project, args.fleet, args.fleet_file)
        if args.list:
            for role in role_names(fleet):
                binding = resolve_runtime_binding(fleet, role, project=args.project)
                if args.agent and binding.get("agent") != args.agent:
                    continue
                if args.kind and binding.get("kind") != args.kind:
                    continue
                if args.group and binding.get("group") != args.group:
                    continue
                print(role)
            return 0
        binding = resolve_runtime_binding(
            fleet,
            args.role[0],
            project=args.project,
            runtime_target=args.runtime_target,
        )
    except FleetScopeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    if args.shell:
        print(shell_output(binding))
    else:
        print(json.dumps(binding, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
