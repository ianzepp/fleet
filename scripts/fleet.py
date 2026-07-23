#!/usr/bin/env python3
"""Fleet chain gate: prepare → prompt → claim → settle → advance.

Mechanical fail-closed gate over the Fleet communication chain. A harness
may spawn anything, but only work with a valid Vivi assignment → claim →
settlement → disposition chain can advance Fleet state.

  fleet prepare --project <root> --to <role> --pass <pass> --scope <scope> \
      --subject '<subject>' --body '<body>' [--node <graph>:<source-id>]
  fleet prompt --project <root> <handle>
  fleet claim  --project <root> <handle> --role <role>
  fleet settle --project <root> <handle> --role <role> --note '<evidence>' \
      <--report <body>|--report-file <path>> [--repo <repo> --tip <sha>] \
      [--verdict <verdict>]
  fleet advance --project <root> --gate <admission|acceptance> \
      --handle <handle> [--json]

Exit codes: 0 ok · 1 chain/gate failure · 2 usage error.

Requires: Python 3.9+ (macOS / Linux), the ``vivi`` binary on PATH.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    add_fleet_scope_arguments,
    load_receipt,
    now_iso,
    require_python,
    run_cmd,
    save_receipt,
    sha256_hex,
)

require_python()

# ---------------------------------------------------------------------------
# Vivi helpers
# ---------------------------------------------------------------------------


def _vivi(
    args: List[str], project: str, *, timeout: float = 30.0
) -> Tuple[int, str]:
    """Run a vivi command with --project; return (rc, combined text)."""
    cmd = ["vivi"] + list(args) + ["--project", str(project)]
    return run_cmd(cmd, timeout=timeout)


def _vivi_json(
    args: List[str], project: str, *, timeout: float = 30.0
) -> Tuple[int, Optional[Any], str]:
    """Run a vivi command requesting JSON; return (rc, parsed-or-None, raw)."""
    cmd = ["vivi"] + list(args) + ["--project", str(project), "--json"]
    rc, out = run_cmd(cmd, timeout=timeout)
    parsed: Optional[Any] = None
    if rc == 0 and out.strip():
        try:
            parsed = json.loads(out)
        except (json.JSONDecodeError, ValueError):
            pass
    return rc, parsed, out


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _print_json(data: Dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _fail(message: str, data: Optional[Dict[str, Any]] = None) -> int:
    """Print error to stderr; optionally print JSON to stdout; return exit 1."""
    if data is not None:
        data["error"] = message
        _print_json(data)
    else:
        print("error: %s" % message, file=sys.stderr)
    return 1


def _canonical_body(body: str) -> str:
    """Normalize Vivi's transport newline without weakening body comparison."""
    return body.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def _identity_local_part(value: str) -> str:
    """Return the local role name from either a role or Vivi address."""
    return value.split("@", 1)[0]


# ---------------------------------------------------------------------------
# Role binding resolution
# ---------------------------------------------------------------------------


def _resolve_role_binding(project: str, role: str) -> Optional[Dict[str, str]]:
    """Get provider/model/harness for a role from Vivi; return None on failure."""
    rc, data, raw = _vivi_json(["role", "show", role], project)
    if rc == 0 and isinstance(data, dict):
        return {
            "provider": str(data.get("provider") or data.get("agent") or ""),
            "model": str(data.get("model") or data.get("agent_model") or ""),
            "harness": str(data.get("harness") or ""),
        }
    # Fallback: parse text output ("model: <slug>" lines)
    if rc == 0 and raw:
        binding: Dict[str, str] = {"provider": "", "model": "", "harness": ""}
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("model:"):
                binding["model"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("provider:"):
                binding["provider"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("harness:"):
                binding["harness"] = stripped.split(":", 1)[1].strip()
        return binding
    return None


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------


VALID_PASSES = frozenset(
    {
        "implement", "review", "goal-forge", "delivery",
        "p1", "p2", "p3", "goal-audit", "delivery-audit", "advisory",
    }
)


def cmd_prepare(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    role = args.role_to

    if not args.scope.strip():
        return _fail("--scope must not be empty")
    if not args.subject.strip():
        return _fail("--subject must not be empty")
    if len(args.depends_on) != len(set(args.depends_on)):
        return _fail("--depends-on handles must be unique")
    role_error = _validate_role_pass(role, args.pass_name)
    if role_error:
        return _fail(role_error)

    if args.body_file:
        try:
            body = Path(args.body_file).read_text(encoding="utf-8")
        except OSError as exc:
            return _fail("cannot read --body-file: %s" % exc)
    else:
        body = args.body
    if not _canonical_body(body).strip():
        return _fail("assignment body must not be empty")

    graph_node = (args.node or "").strip() or None
    if graph_node:
        node_err = _validate_ready_graph_node(str(project), graph_node)
        if node_err:
            return _fail(node_err)

    # 1. Resolve expected role binding
    binding = _resolve_role_binding(str(project), role)
    if binding is None:
        return _fail("cannot resolve role binding for %r" % role)
    if not binding.get("model"):
        return _fail("role %r has no model in its Vivi record" % role)

    # 2. Create the Vivi task
    task_args = [
        "task", "send",
        "--from", "mind",
        "--to", role,
        "--subject", args.subject,
        "--body", body,
    ]
    for dependency in args.depends_on:
        if load_receipt(str(project), dependency) is None:
            return _fail("dependency %r has no fleet prepare receipt" % dependency)
        task_args.extend(["--depends-on", dependency])
    rc, out = _vivi(task_args, str(project))
    if rc != 0:
        return _fail("vivi task send failed: %s" % out.strip())

    # 3. Parse handle from vivi output
    handle = _parse_handle_from_send_output(out, role)
    if not handle:
        return _fail(
            "cannot parse task handle from vivi output: %s" % out.strip()
        )

    # 4. Hash the assignment body
    body_hash = sha256_hex(_canonical_body(body))

    # 5. Write sidecar receipt, including the exact prompt for later re-wake.
    boot = _format_boot_prompt(handle, role, project, args.pass_name)
    receipt: Dict[str, Any] = {
        "handle": handle,
        "kind": "task",
        "role": role,
        "scope": args.scope or "",
        "pass": args.pass_name,
        "depends_on": list(args.depends_on),
        "expected_role_binding": binding,
        "assignment_body_hash": body_hash,
        "prepared_at": now_iso(),
        "prepared_by": "mind",
        "boot_prompt": boot,
        "claim": None,
        "settlement": None,
    }
    if graph_node:
        receipt["graph_node"] = graph_node
    save_receipt(str(project), handle, receipt)

    # 6. Print boot prompt
    print(boot)
    return 0


def _validate_ready_graph_node(project: str, node_ref: str) -> str:
    """Return error text unless node_ref is in the graph's ready frontier."""
    if ":" not in node_ref:
        return "--node must be graph:source-id (got %r)" % node_ref
    graph_code, source_id = node_ref.split(":", 1)
    if not graph_code or not source_id:
        return "--node must be graph:source-id (got %r)" % node_ref
    rc, data, raw = _vivi_json(["graph", "ready", graph_code], project)
    if rc != 0 or data is None:
        return "vivi graph ready failed for %r: %s" % (graph_code, raw.strip())
    if not isinstance(data, dict):
        return "vivi graph ready returned an invalid frontier for %r" % graph_code
    frontiers = {}
    for name in ("ready", "blocked", "active"):
        values = data.get(name)
        if not isinstance(values, list) or not all(
            isinstance(value, str) for value in values
        ):
            return "vivi graph ready returned no %s frontier for %r" % (
                name,
                graph_code,
            )
        frontiers[name] = values
    if source_id in frontiers["ready"]:
        return ""
    if source_id in frontiers["active"]:
        return "cannot prepare graph node %r: already active" % node_ref
    if source_id in frontiers["blocked"]:
        return "cannot prepare blocked graph node %r" % node_ref
    return (
        "graph node %r is not in the open frontier on %r "
        "(possibly terminal or missing)" % (source_id, graph_code)
    )


def _validate_role_pass(role: str, pass_name: str) -> str:
    if role.startswith("planner-"):
        allowed = {"goal-forge", "delivery", "p1", "p2", "p3"}
    elif role.startswith("auditor-"):
        allowed = {"review", "goal-audit", "delivery-audit"}
    elif role.startswith("hand-"):
        allowed = {"implement"}
    elif role.startswith("head-"):
        allowed = {"advisory"}
    else:
        return "unsupported fleet role %r" % role
    if pass_name not in allowed:
        return "role %r cannot claim pass %r" % (role, pass_name)
    return ""


def _parse_handle_from_send_output(output: str, role: str = "") -> str:
    """Extract a task handle from vivi task send output.

    Tries JSON first, then Vivi's recipient-copy output, then a lone handle.
    """
    stripped = output.strip()
    if not stripped:
        return ""
    # Try JSON
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            for key in ("handle", "id", "task"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        if isinstance(data, str):
            return data.strip()
    except (json.JSONDecodeError, ValueError):
        pass
    # Vivi prints one recipient copy followed by the sender copy:
    #   created hand-1 3256f67d
    #   sent 93441a2b
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    for line in lines:
        fields = line.split()
        if len(fields) == 3 and fields[0] in ("created", "delivered", "replied"):
            if not role or _identity_local_part(fields[1]) == role:
                return fields[2]
    if len(lines) == 1:
        fields = lines[0].split()
        if len(fields) == 1:
            return fields[0]
    return ""


def _format_boot_prompt(
    handle: str, role: str, project: Path, pass_name: str
) -> str:
    """Format the thin boot prompt delivered to the spawned role."""
    root = str(project)
    protocol = _protocol_for_role(role)
    lines = [
        "You are fleet role %s." % role,
        "Read %s before acting." % protocol,
        "",
        "Chain gate (run these exactly):",
        "  1. Claim this assignment:",
        "     python3 %s claim %s --role %s --project %s"
        % (_script_name(), handle, role, root),
        "  2. Load your charter and the named assignment:",
        "     vivi role charter show %s --project %s" % (role, root),
        "     vivi task show %s --project %s" % (handle, root),
        "  3. Do the work per your role protocol.",
        "  4. Settle; this completes the task and replies with the durable report:",
        "     python3 %s settle %s --role %s --project %s "
        "--note '<evidence>' --report-file <path>"
        % (_script_name(), handle, role, root),
        "",
        "Refuse to work if claiming fails. Do not skip settlement.",
        "Pass: %s" % pass_name,
    ]
    return "\n".join(lines)


def _protocol_for_role(role: str) -> str:
    root = Path(__file__).resolve().parent.parent / "references"
    if role.startswith("planner-"):
        name = "planner-protocol.md"
    elif role.startswith("auditor-"):
        name = "auditor-protocol.md"
    elif role.startswith("head-"):
        name = "head-protocol.md"
    else:
        name = "hand-protocol.md"
    return str(root / name)


def cmd_prompt(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    receipt = load_receipt(str(project), args.handle)
    if receipt is None:
        return _fail("no prepare receipt for handle %r" % args.handle)
    boot = receipt.get("boot_prompt")
    if not isinstance(boot, str) or not boot:
        return _fail("prepare receipt has no captured prompt for %r" % args.handle)
    print(boot)
    return 0


def _script_name() -> str:
    """Return the invocation path for fleet.py in boot prompts."""
    return str(Path(__file__).resolve())


# ---------------------------------------------------------------------------
# claim
# ---------------------------------------------------------------------------


def cmd_claim(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    handle = args.handle
    role = args.role

    # 1. Load sidecar receipt
    receipt = load_receipt(str(project), handle)
    if receipt is None:
        return _fail("no prepare receipt for handle %r" % handle)
    if receipt.get("role") != role:
        return _fail(
            "handle %r was prepared for %r, not %r"
            % (handle, receipt.get("role"), role)
        )

    # 2. Show the Vivi task
    rc, task_data, task_raw = _vivi_json(["task", "show", handle], str(project))
    if rc != 0:
        return _fail("vivi task show failed for %r: %s" % (handle, task_raw.strip()))

    # 3. Verify the task
    task = _parse_task(task_data, task_raw)
    if task is None:
        return _fail("cannot parse task from vivi output")

    # Verify task is addressed to this role
    task_to = _identity_local_part(task.get("to", ""))
    if task_to and task_to != role:
        return _fail(
            "task %r is addressed to %r, not %r" % (handle, task_to, role)
        )

    # Verify task body hash matches the frozen receipt
    task_body = task.get("body", "")
    live_hash = sha256_hex(_canonical_body(task_body))
    frozen_hash = receipt.get("assignment_body_hash", "")
    if frozen_hash and live_hash != frozen_hash:
        return _fail(
            "assignment body hash mismatch: task body changed after prepare "
            "(expected %s, got %s)" % (frozen_hash, live_hash)
        )

    # 4. Verify role binding
    expected = receipt.get("expected_role_binding", {})
    live_binding = _resolve_role_binding(str(project), role)
    if live_binding is None:
        return _fail("cannot resolve live role binding for %r" % role)
    if expected:
        for key in ("provider", "model", "harness"):
            exp_val = expected.get(key, "")
            live_val = live_binding.get(key, "")
            if exp_val != live_val:
                return _fail(
                    "role binding mismatch for %r: expected %s=%r, got %r"
                    % (role, key, exp_val, live_val)
                )

    task_status = task.get("status", "")
    if task_status in ("done", "completed", "closed"):
        return _fail("task %r is already done" % handle)

    # 5. Check claim state
    existing_claim = receipt.get("claim")
    if existing_claim is not None:
        claimed_by = existing_claim.get("role", "")
        if claimed_by == role:
            print("Already claimed by %s." % role)
            return 0
        return _fail("handle %r already claimed by %r" % (handle, claimed_by))

    # 6. File Vivi reply first. A missing durable edge must not leave a valid claim.
    claim_entry: Dict[str, Any] = {
        "role": role,
        "claimed_at": now_iso(),
        "binding_verified": True,
    }
    reply_body = "fleet: claimed at %s" % claim_entry["claimed_at"]
    rc, out = _vivi(
        ["mail", "reply", handle, "--from", role, "--body", reply_body],
        str(project),
    )
    if rc != 0:
        return _fail(
            "vivi claim reply failed; claim not recorded: %s" % out.strip()
        )
    claim_entry["reply_handle"] = _parse_handle_from_send_output(out)
    receipt["claim"] = claim_entry
    save_receipt(str(project), handle, receipt)

    # 7. If prepared for a work-graph node, activate only after a durable claim.
    graph_node = receipt.get("graph_node")
    if graph_node:
        act_rc, act_out = _vivi(
            [
                "graph", "activate", str(graph_node),
                "--task", handle,
            ],
            str(project),
        )
        if act_rc != 0:
            return _fail(
                "claimed %s but vivi graph activate failed for %r: %s"
                % (handle, graph_node, act_out.strip())
            )
        claim_entry["graph_activated"] = True
        receipt["claim"] = claim_entry
        save_receipt(str(project), handle, receipt)

    print("Claimed %s as %s." % (handle, role))
    return 0


def _parse_task(data: Any, raw: str) -> Optional[Dict[str, Any]]:
    """Parse a vivi task show result into {to, body, status}.

    Handles both JSON dict and text fallback.
    """
    item: Optional[Dict[str, Any]] = None
    if isinstance(data, dict):
        item = data
    elif isinstance(data, list):
        item = next(
            (
                row
                for row in data
                if isinstance(row, dict) and row.get("kind") == "task"
            ),
            None,
        )
    if item is not None:
        return {
            "to": str(item.get("to") or item.get("assignee") or ""),
            "body": str(item.get("body") or item.get("content") or ""),
            "status": str(item.get("status") or item.get("role") or "").lower(),
        }
    # Text fallback: parse "field: value" lines
    result: Dict[str, str] = {"to": "", "body": "", "status": ""}
    if raw:
        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("to:"):
                result["to"] = stripped.split(":", 1)[1].strip()
            elif stripped.lower().startswith("status:"):
                result["status"] = stripped.split(":", 1)[1].strip().lower()
            elif stripped.lower().startswith("body:"):
                result["body"] = stripped.split(":", 1)[1].strip()
    return result


# ---------------------------------------------------------------------------
# settle
# ---------------------------------------------------------------------------


def cmd_settle(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    handle = args.handle
    role = args.role

    if bool(args.repo) != bool(args.tip):
        return _fail("--repo and --tip must be supplied together")
    if not args.note.strip():
        return _fail("--note must not be empty")

    # 1. Load sidecar and verify claim
    receipt = load_receipt(str(project), handle)
    if receipt is None:
        return _fail("no prepare receipt for handle %r" % handle)

    claim = receipt.get("claim")
    if claim is None:
        return _fail("cannot settle %r: not yet claimed" % handle)
    if claim.get("role") != role:
        return _fail(
            "cannot settle %r: claimed by %r, not %r"
            % (handle, claim.get("role"), role)
        )

    # 2. Fail on double-settle
    if receipt.get("settlement") is not None:
        return _fail("handle %r already settled" % handle)

    receipt_pass = receipt.get("pass")
    if receipt_pass in ("review", "goal-audit", "delivery-audit") and not args.verdict:
        return _fail("pass %r requires --verdict" % receipt_pass)
    if args.report_file:
        try:
            report_body = Path(args.report_file).read_text(encoding="utf-8")
        except OSError as exc:
            return _fail("cannot read --report-file: %s" % exc)
    else:
        report_body = args.report
    if not _canonical_body(report_body).strip():
        return _fail("report must not be empty")

    # 3. Complete the task if this is the first settle attempt.
    rc, task_data, task_raw = _vivi_json(["task", "show", handle], str(project))
    if rc != 0:
        return _fail("vivi task show failed: %s" % task_raw.strip())

    task = _parse_task(task_data, task_raw)
    if task is None:
        return _fail("cannot parse task from vivi output")

    task_status = task.get("status", "")
    task_done = _is_task_done(task_status, handle, role, str(project))
    if not task_done:
        done_args = ["task", "done", handle, "--for", role, "--note", args.note]
        if args.verdict:
            done_args.extend(["--verdict", args.verdict])
        if args.repo and args.tip:
            done_args.extend(["--repo", args.repo, "--tip", args.tip])
        rc, out = _vivi(done_args, str(project))
        if rc != 0:
            return _fail("vivi task done failed: %s" % out.strip())
        rc, task_data, task_raw = _vivi_json(
            ["task", "show", handle], str(project)
        )
        task = _parse_task(task_data, task_raw)
        if rc != 0 or task is None or not _is_task_done(
            task.get("status", ""), handle, role, str(project)
        ):
            return _fail("task %r did not reach done state" % handle)

    # 4. Create the report reply if a previous partial settle did not.
    report_handle = _find_report_mail(handle, role, str(project), task_data)
    if report_handle is None:
        report_payload = "fleet-report:\n%s" % report_body
        rc, out = _vivi(
            ["mail", "reply", handle, "--from", role, "--body", report_payload],
            str(project),
        )
        if rc != 0:
            return _fail("vivi report reply failed: %s" % out.strip())
        rc, refreshed_data, _ = _vivi_json(
            ["task", "show", handle], str(project)
        )
        report_handle = (
            _find_report_mail(handle, role, str(project), refreshed_data)
            if rc == 0
            else None
        )
        if report_handle is None:
            report_handle = _parse_handle_from_send_output(out)
        if not report_handle:
            return _fail(
                "cannot parse report handle from vivi output: %s" % out.strip()
            )

    # 5. Write settlement entry
    settlement: Dict[str, Any] = {
        "settled_at": now_iso(),
        "task_done_verified": True,
        "report_handle": report_handle,
        "git_repo": args.repo or None,
        "git_tip": args.tip or None,
        "verdict": args.verdict or None,
        "scope_declared": receipt.get("scope", ""),
    }
    receipt["settlement"] = settlement
    save_receipt(str(project), handle, receipt)

    print("Settled %s." % handle)
    return 0


def _is_task_done(
    status: str, handle: str, role: str, project: str
) -> bool:
    """Check whether a task is done, with fallback to list query."""
    if status in ("done", "completed", "closed"):
        return True
    if status in ("open", "pending", "active", "task", "tasks"):
        return False
    # Fallback: check if handle appears in done task list
    rc, out, _ = _vivi_json(
        ["task", "list", "--for", role, "--status", "done"], project
    )
    if rc == 0 and isinstance(out, list):
        for item in out:
            if isinstance(item, dict) and item.get("handle") == handle:
                return True
            if isinstance(item, str) and handle in item:
                return True
    return False


def _find_report_mail(
    handle: str, role: str, project: str, task_data: Any
) -> Optional[str]:
    """Find a report mail from role referencing the handle.

    The report must be a captured reply in the task thread. The lightweight
    ``fleet: claimed`` reply is not a report.
    """
    rows = task_data if isinstance(task_data, list) else []
    for item in reversed(rows):
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "mail":
            continue
        sender = _identity_local_part(str(item.get("from") or ""))
        recipient = _identity_local_part(str(item.get("to") or ""))
        if sender != role:
            continue
        if recipient != "mind":
            continue
        body = _canonical_body(str(item.get("body") or ""))
        if not body.startswith("fleet-report:\n"):
            continue
        mail_handle = str(item.get("handle") or item.get("id") or "")
        if mail_handle:
            return mail_handle

    # Fallback for Vivi versions whose task-show JSON omits thread replies.
    rc, trace_data, _ = _vivi_json(
        ["trace", handle, "--max-depth", "3"], project
    )
    if isinstance(trace_data, dict):
        for node in reversed(trace_data.get("nodes", [])):
            if not isinstance(node, dict):
                continue
            body = _canonical_body(str(node.get("body") or ""))
            if not body.startswith("fleet-report:\n"):
                continue
            for message in node.get("messages", []):
                if not isinstance(message, dict) or message.get("kind") != "mail":
                    continue
                sender = _identity_local_part(str(message.get("from") or ""))
                recipient = _identity_local_part(str(message.get("to") or ""))
                if sender == role and recipient == "mind":
                    value = str(
                        node.get("handle") or message.get("handle") or ""
                    )
                    return value or None

    return None


# ---------------------------------------------------------------------------
# advance
# ---------------------------------------------------------------------------

VALID_GATES = frozenset({"admission", "acceptance"})


def cmd_advance(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    handle = args.handle
    gate = args.gate

    result = _check_chain(str(project), handle, gate)
    if args.json:
        _print_json(result)
    else:
        if result["verdict"] == "pass":
            print("PASS: %s gate for %s" % (gate, handle))
        else:
            reasons = "; ".join(result.get("gaps", [])) or "unknown"
            print("FAIL: %s gate for %s: %s" % (gate, handle, reasons))
    return 0 if result["verdict"] == "pass" else 1


def _check_chain(project: str, handle: str, gate: str) -> Dict[str, Any]:
    """Verify the terminal assignment and every declared dependency."""
    gaps: List[str] = []
    receipts: Dict[str, Dict[str, Any]] = {}
    _validate_assignment(project, handle, receipts, gaps, set())
    terminal = receipts.get(handle)
    if terminal is None:
        return _fail_result(gate, handle, {"assignments": receipts}, gaps)

    terminal_pass = str(terminal.get("pass") or "")
    terminal_role = str(terminal.get("role") or "")
    terminal_verdict = str(terminal.get("verdict") or "")
    passes = {str(receipt.get("pass") or "") for receipt in receipts.values()}

    if gate == "acceptance":
        if terminal_pass != "review" or not terminal_role.startswith("auditor-"):
            gaps.append("acceptance terminal must be an auditor review assignment")
        if terminal_verdict != "clean_pass":
            gaps.append("acceptance requires terminal clean_pass verdict")
        if not (terminal.get("git_repo") and terminal.get("git_tip")):
            gaps.append("acceptance review lacks repo/tip receipt")
        if "implement" not in passes:
            gaps.append("acceptance review must depend on an implement assignment")
        elif not any(
            receipt.get("pass") == "implement"
            and receipt.get("git_repo") == terminal.get("git_repo")
            and receipt.get("git_tip") == terminal.get("git_tip")
            for receipt in receipts.values()
        ):
            gaps.append(
                "acceptance review repo/tip does not match an implement receipt"
            )

    elif gate == "admission":
        if terminal_pass != "delivery-audit" or not terminal_role.startswith(
            "auditor-"
        ):
            gaps.append(
                "admission terminal must be an auditor delivery-audit assignment"
            )
        if terminal_verdict != "clean_pass":
            gaps.append("admission requires terminal clean_pass verdict")
        if "p1" not in passes:
            gaps.append("missing P1 intent receipt")
        if "p2" not in passes:
            gaps.append("missing P2 goal receipt")
        if "goal-audit" not in passes:
            gaps.append("missing goal-reality audit receipt")
        if "p3" not in passes:
            gaps.append("missing P3 delivery receipt")

    if gaps:
        return _fail_result(gate, handle, {"assignments": receipts}, gaps)

    return {
        "verdict": "pass",
        "gate": gate,
        "handle": handle,
        "chain": {"assignments": receipts},
        "gaps": [],
    }


def _validate_assignment(
    project: str,
    handle: str,
    receipts: Dict[str, Dict[str, Any]],
    gaps: List[str],
    visiting: set,
) -> None:
    """Validate one receipt against live Vivi state, then its dependencies."""
    if handle in visiting:
        gaps.append("dependency cycle at %s" % handle)
        return
    if handle in receipts:
        return
    visiting.add(handle)

    receipt = load_receipt(project, handle)
    if receipt is None:
        gaps.append("%s: no prepare receipt" % handle)
        visiting.remove(handle)
        return

    summary: Dict[str, Any] = {
        "role": receipt.get("role"),
        "pass": receipt.get("pass"),
        "depends_on": list(receipt.get("depends_on") or []),
        "prepared_at": receipt.get("prepared_at"),
    }
    receipts[handle] = summary

    claim = receipt.get("claim")
    settlement = receipt.get("settlement")
    role = str(receipt.get("role") or "")
    pass_name = str(receipt.get("pass") or "")
    role_pass_error = _validate_role_pass(role, pass_name)
    if role_pass_error:
        gaps.append("%s: %s" % (handle, role_pass_error))
    if not isinstance(claim, dict):
        gaps.append("%s: no claim recorded" % handle)
    elif claim.get("role") != role:
        gaps.append("%s: claim role does not match assignment role" % handle)
    else:
        summary["claimed_at"] = claim.get("claimed_at")
    if not isinstance(settlement, dict):
        gaps.append("%s: no settlement recorded" % handle)
    else:
        summary["settled_at"] = settlement.get("settled_at")
        summary["report_handle"] = settlement.get("report_handle")
        summary["verdict"] = settlement.get("verdict")
        summary["git_repo"] = settlement.get("git_repo")
        summary["git_tip"] = settlement.get("git_tip")
        if settlement.get("scope_declared") != receipt.get("scope"):
            gaps.append("%s: settlement scope differs from prepared scope" % handle)
        if receipt.get("pass") == "implement" and not (
            settlement.get("git_repo") and settlement.get("git_tip")
        ):
            gaps.append("%s: implement settlement lacks repo/tip receipt" % handle)

    rc, task_data, task_raw = _vivi_json(["task", "show", handle], project)
    task = _parse_task(task_data, task_raw)
    if rc != 0 or task is None:
        gaps.append("%s: cannot retrieve live Vivi task" % handle)
    else:
        task_role = _identity_local_part(task.get("to", ""))
        if task_role and task_role != role:
            gaps.append("%s: live task role mismatch" % handle)
        live_hash = sha256_hex(_canonical_body(task.get("body", "")))
        if receipt.get("assignment_body_hash") != live_hash:
            gaps.append("%s: assignment body hash mismatch" % handle)
        if not _is_task_done(task.get("status", ""), handle, role, project):
            gaps.append("%s: task is not done" % handle)

    rc, trace_data, _ = _vivi_json(
        ["trace", handle, "--max-depth", "5"], project, timeout=45.0
    )
    if rc != 0 or not isinstance(trace_data, dict):
        gaps.append("%s: cannot retrieve Vivi trace" % handle)
    elif isinstance(settlement, dict):
        report_handle = str(settlement.get("report_handle") or "")
        trace_handles = {
            str(node.get("handle") or "")
            for node in trace_data.get("nodes", [])
            if isinstance(node, dict)
        }
        if not report_handle or report_handle not in trace_handles:
            gaps.append("%s: settlement report is not in Vivi trace" % handle)

    for dependency in receipt.get("depends_on") or []:
        _validate_assignment(project, str(dependency), receipts, gaps, visiting)
    visiting.remove(handle)


def _fail_result(
    gate: str, handle: str, chain: Dict[str, Any], gaps: List[str]
) -> Dict[str, Any]:
    return {
        "verdict": "fail",
        "gate": gate,
        "handle": handle,
        "chain": chain,
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fleet",
        description="Fleet chain gate: prepare → prompt → claim → settle → advance.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # prepare
    prep = sub.add_parser("prepare", help="Create assignment + frozen receipt")
    add_fleet_scope_arguments(prep, required_project=True)
    prep.add_argument("--to", dest="role_to", required=True, help="assignee role")
    prep.add_argument(
        "--pass", dest="pass_name", required=True,
        choices=sorted(VALID_PASSES),
        help="role pass; see references/fleet-helper.md for the role/pass matrix",
    )
    prep.add_argument("--scope", required=True, help="declared work/write scope")
    prep.add_argument(
        "--depends-on", action="append", default=[],
        help="prepared assignment handle this work depends on; repeatable",
    )
    prep.add_argument(
        "--node",
        default=None,
        help="ready Vivi work-graph node as graph:source-id; activate on claim",
    )
    prep.add_argument("--subject", required=True, help="task subject")
    body = prep.add_mutually_exclusive_group(required=True)
    body.add_argument("--body", help="task body")
    body.add_argument("--body-file", help="read body from file")
    prep.set_defaults(func=cmd_prepare)

    # prompt
    prompt = sub.add_parser("prompt", help="Reprint a prepared boot prompt")
    add_fleet_scope_arguments(prompt, required_project=True)
    prompt.add_argument("handle", help="Vivi task handle")
    prompt.set_defaults(func=cmd_prompt)

    # claim
    claim = sub.add_parser("claim", help="Claim an assignment")
    add_fleet_scope_arguments(claim, required_project=True)
    claim.add_argument("handle", help="Vivi task handle")
    claim.add_argument("--role", required=True, help="claiming role")
    claim.set_defaults(func=cmd_claim)

    # settle
    settle = sub.add_parser("settle", help="Record settlement evidence")
    add_fleet_scope_arguments(settle, required_project=True)
    settle.add_argument("handle", help="Vivi task handle")
    settle.add_argument("--role", required=True, help="settling role")
    settle.add_argument("--repo", default=None, help="git repository receipt")
    settle.add_argument("--tip", default=None, help="git commit SHA receipt")
    settle.add_argument("--note", required=True, help="concise completion evidence")
    report = settle.add_mutually_exclusive_group(required=True)
    report.add_argument("--report", help="durable report body")
    report.add_argument("--report-file", help="read durable report from file")
    settle.add_argument(
        "--verdict", choices=("clean_pass", "residual", "block_ship"),
        default=None, help="audit verdict",
    )
    settle.set_defaults(func=cmd_settle)

    # advance
    adv = sub.add_parser("advance", help="Check chain gate (pure read)")
    add_fleet_scope_arguments(adv, required_project=True)
    adv.add_argument("--gate", required=True, choices=sorted(VALID_GATES))
    adv.add_argument("--handle", required=True, help="Vivi task handle")
    adv.add_argument("--json", action="store_true", help="machine-readable output")
    adv.set_defaults(func=cmd_advance)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
