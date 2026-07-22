#!/usr/bin/env python3
"""Fleet chain gate: prepare → claim → settle → advance.

Mechanical fail-closed gate over the Fleet communication chain. A harness
may spawn anything, but only work with a valid Vivi assignment → claim →
settlement → disposition chain can advance Fleet state.

  fleet prepare --project <root> --to <role> --pass <pass> --scope <scope> \
      --subject '<subject>' --body '<body>'
  fleet claim  --project <root> <handle> --role <role>
  fleet settle --project <root> <handle> --role <role> [--repo <repo>] \
      [--tip <sha>] [--verdict <verdict>] [--scope <scope>]
  fleet advance --project <root> --gate <admission|acceptance> --handle <handle> [--json]

Exit codes: 0 ok · 1 chain/gate failure · 2 usage error.

Requires: Python 3.9+ (macOS / Linux), the ``vivi`` binary on PATH.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_common import (  # noqa: E402
    FleetScopeError,
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
    {"implement", "review", "goal-forge", "delivery", "p1", "p2", "p3"}
)


def cmd_prepare(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    role = args.role_to

    if args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    else:
        body = args.body

    # 1. Resolve expected role binding
    binding = _resolve_role_binding(str(project), role)
    if binding is None:
        return _fail("cannot resolve role binding for %r" % role)
    if not binding.get("model"):
        print(
            "warning: role %r has no model in its Vivi record" % role,
            file=sys.stderr,
        )

    # 2. Create the Vivi task
    task_args = [
        "task", "send",
        "--from", "mind",
        "--to", role,
        "--subject", args.subject,
        "--body", body,
    ]
    rc, out = _vivi(task_args, str(project))
    if rc != 0:
        return _fail("vivi task send failed: %s" % out.strip())

    # 3. Parse handle from vivi output
    handle = _parse_handle_from_send_output(out)
    if not handle:
        return _fail(
            "cannot parse task handle from vivi output: %s" % out.strip()
        )

    # 4. Hash the assignment body
    body_hash = sha256_hex(body)

    # 5. Write sidecar receipt
    receipt: Dict[str, Any] = {
        "handle": handle,
        "kind": "task",
        "role": role,
        "scope": args.scope or "",
        "pass": args.pass_name,
        "expected_role_binding": binding,
        "assignment_body_hash": body_hash,
        "prepared_at": now_iso(),
        "prepared_by": "mind",
        "claim": None,
        "settlement": None,
    }
    save_receipt(str(project), handle, receipt)

    # 6. Print boot prompt
    boot = _format_boot_prompt(handle, role, project, args.pass_name)
    print(boot)
    return 0


def _parse_handle_from_send_output(output: str) -> str:
    """Extract a task handle from vivi task send output.

    Tries JSON first; falls back to the last non-empty line.
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
    # Fallback: last non-empty line
    lines = [ln.strip() for ln in stripped.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _format_boot_prompt(
    handle: str, role: str, project: Path, pass_name: str
) -> str:
    """Format the thin boot prompt delivered to the spawned role."""
    root = str(project)
    lines = [
        "You are fleet role %s." % role,
        "",
        "Chain gate (run these exactly):",
        "  1. Claim this assignment:",
        "     python3 %s claim %s --role %s --project %s"
        % (_script_name(), handle, role, root),
        "  2. Do the work per your role protocol.",
        "  3. Before returning, settle:",
        "     python3 %s settle %s --role %s --project %s"
        % (_script_name(), handle, role, root),
        "",
        "Refuse to work if claiming fails. Do not skip settlement.",
        "Pass: %s" % pass_name,
    ]
    return "\n".join(lines)


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

    # 2. Show the Vivi task
    rc, task_data, task_raw = _vivi_json(["task", "show", handle], str(project))
    if rc != 0:
        return _fail("vivi task show failed for %r: %s" % (handle, task_raw.strip()))

    # 3. Verify the task
    task = _parse_task(task_data, task_raw)
    if task is None:
        return _fail("cannot parse task from vivi output")

    # Verify task is addressed to this role
    task_to = task.get("to", "")
    if task_to and task_to != role:
        return _fail(
            "task %r is addressed to %r, not %r" % (handle, task_to, role)
        )

    # Verify task body hash matches the frozen receipt
    task_body = task.get("body", "")
    live_hash = sha256_hex(task_body)
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
            if exp_val and live_val and exp_val != live_val:
                return _fail(
                    "role binding mismatch for %r: expected %s=%r, got %r"
                    % (role, key, exp_val, live_val)
                )

    # 5. Check claim state
    existing_claim = receipt.get("claim")
    if existing_claim is not None:
        claimed_by = existing_claim.get("role", "")
        if claimed_by == role:
            print("Already claimed by %s." % role)
            return 0
        return _fail("handle %r already claimed by %r" % (handle, claimed_by))

    # 6. Write claim entry
    claim_entry: Dict[str, Any] = {
        "role": role,
        "claimed_at": now_iso(),
        "pid": os.getpid(),
        "binding_verified": True,
    }
    receipt["claim"] = claim_entry
    save_receipt(str(project), handle, receipt)

    # 7. File Vivi mail reply to create a trace edge
    reply_body = "fleet: claimed at %s" % claim_entry["claimed_at"]
    rc, out = _vivi(
        ["mail", "reply", handle, "--from", role, "--body", reply_body],
        str(project),
    )
    if rc != 0:
        print(
            "warning: vivi mail reply failed (claim still recorded): %s"
            % out.strip(),
            file=sys.stderr,
        )

    print("Claimed %s as %s." % (handle, role))
    return 0


def _parse_task(data: Any, raw: str) -> Optional[Dict[str, Any]]:
    """Parse a vivi task show result into {to, body, status}.

    Handles both JSON dict and text fallback.
    """
    if isinstance(data, dict):
        return {
            "to": str(data.get("to") or data.get("assignee") or ""),
            "body": str(data.get("body") or data.get("content") or ""),
            "status": str(data.get("status") or "").lower(),
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

    # 3. Verify task is done
    rc, task_data, task_raw = _vivi_json(["task", "show", handle], str(project))
    if rc != 0:
        return _fail("vivi task show failed: %s" % task_raw.strip())

    task = _parse_task(task_data, task_raw)
    if task is None:
        return _fail("cannot parse task from vivi output")

    task_status = task.get("status", "")
    task_done = _is_task_done(task_status, handle, role, str(project))
    if not task_done:
        return _fail(
            "task %r is not done (status: %s)" % (handle, task_status or "unknown")
        )

    # 4. Verify report mail exists
    report_handle = _find_report_mail(handle, role, str(project))
    if report_handle is None:
        return _fail(
            "no report mail from %r referencing handle %r found"
            % (role, handle)
        )

    # 5. Write settlement entry
    settlement: Dict[str, Any] = {
        "settled_at": now_iso(),
        "task_done_verified": True,
        "report_handle": report_handle,
        "git_repo": args.repo or None,
        "git_tip": args.tip or None,
        "verdict": args.verdict or None,
        "scope_declared": args.scope or receipt.get("scope", ""),
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
    if status in ("open", "pending", "active"):
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


def _find_report_mail(handle: str, role: str, project: str) -> Optional[str]:
    """Find a report mail from role referencing the handle.

    Checks vivi mail list for a mail from role to mind that references
    the handle in subject or body. Falls back to trace inspection.
    """
    rc, data, raw = _vivi_json(["mail", "list", "--for", "mind"], project)
    mails: List[Any] = []
    if isinstance(data, list):
        mails = data
    elif isinstance(data, dict):
        mails = data.get("items", data.get("mails", []))

    for item in mails:
        if not isinstance(item, dict):
            continue
        sender = str(item.get("from") or item.get("sender") or "")
        if sender != role:
            continue
        subject = str(item.get("subject") or "")
        body = str(item.get("body") or "")
        mail_handle = str(item.get("handle") or item.get("id") or "")
        if handle in subject or handle in body:
            return mail_handle
        # Check reply-to edge: mail whose reply-to is the task handle
        reply_to = str(item.get("reply_to") or item.get("in_reply_to") or "")
        if reply_to == handle:
            return mail_handle

    # Fallback: check trace for a mail edge from the role
    rc, trace_data, _ = _vivi_json(
        ["trace", handle, "--max-depth", "3"], project
    )
    if isinstance(trace_data, dict):
        edges = trace_data.get("edges", [])
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            edge_kind = str(edge.get("kind") or edge.get("type") or "")
            source = str(edge.get("source") or edge.get("from") or "")
            target = str(edge.get("target") or edge.get("to") or "")
            if "mail" in edge_kind and role in (source, target):
                node_handle = target if role in source else source
                if node_handle:
                    return node_handle

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
    """Pure-read chain and gate verification. Returns structured result."""
    gaps: List[str] = []
    chain: Dict[str, Any] = {}

    # 1. Load sidecar receipt
    receipt = load_receipt(project, handle)
    if receipt is None:
        return {
            "verdict": "fail",
            "gate": gate,
            "handle": handle,
            "chain": {},
            "gaps": ["no prepare receipt for handle"],
        }
    chain["prepared_at"] = receipt.get("prepared_at")
    chain["role"] = receipt.get("role")

    # 2. Verify chain completeness
    claim = receipt.get("claim")
    if claim is None:
        gaps.append("no claim recorded")
    else:
        chain["claimed_at"] = claim.get("claimed_at")
        chain["claimed_by"] = claim.get("role")

    settlement = receipt.get("settlement")
    if settlement is None:
        gaps.append("no settlement recorded")
    else:
        chain["settled_at"] = settlement.get("settled_at")
        chain["report_handle"] = settlement.get("report_handle")

    if gaps:
        return _fail_result(gate, handle, chain, gaps)

    # 3. Cross-check hash against live task body
    frozen_hash = receipt.get("assignment_body_hash", "")
    rc, task_data, _ = _vivi_json(["task", "show", handle], project)
    task = _parse_task(task_data, "")
    if task is not None:
        live_hash = sha256_hex(task.get("body", ""))
        if frozen_hash and live_hash != frozen_hash:
            gaps.append("assignment body hash mismatch (mutated after prepare)")

    # 4. Walk Vivi trace
    trace_edges = _get_trace_edges(handle, project)
    if trace_edges is None:
        gaps.append("cannot retrieve vivi trace for handle")
    else:
        has_task_done = any(
            _is_task_done_edge(e) for e in trace_edges
        )
        if not has_task_done:
            gaps.append("no task-done edge in trace")

        has_report = any(
            _is_report_edge(e, receipt.get("role", "")) for e in trace_edges
        )
        if not has_report:
            gaps.append("no report mail edge in trace")

    if gaps:
        return _fail_result(gate, handle, chain, gaps)

    # 5. Gate-specific evidence
    if gate == "acceptance":
        verdict_found = _check_acceptance_evidence(trace_edges, handle, project)
        if verdict_found is not None:
            chain["audit_verdict"] = verdict_found
        else:
            gaps.append("no audit verdict (clean_pass or residual) in chain")

    elif gate == "admission":
        audit_results = _check_admission_evidence(trace_edges, handle, project)
        chain["audits"] = audit_results
        if not audit_results.get("p2"):
            gaps.append("missing P2 goal-reality audit receipt")
        if not audit_results.get("p3"):
            gaps.append("missing P3 delivery-reality audit receipt")

    if gaps:
        return _fail_result(gate, handle, chain, gaps)

    return {
        "verdict": "pass",
        "gate": gate,
        "handle": handle,
        "chain": chain,
        "gaps": [],
    }


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


def _get_trace_edges(handle: str, project: str) -> Optional[List[Dict[str, Any]]]:
    """Return trace edges for a handle, or None on failure."""
    rc, data, _ = _vivi_json(
        ["trace", handle, "--max-depth", "5"], project, timeout=45.0
    )
    if rc != 0 or not isinstance(data, dict):
        return None
    edges = data.get("edges", [])
    return edges if isinstance(edges, list) else []


def _is_task_done_edge(edge: Dict[str, Any]) -> bool:
    """Check whether a trace edge represents a task-done lifecycle event."""
    kind = str(edge.get("kind") or edge.get("type") or "").lower()
    if "event" in kind and "done" in kind:
        return True
    label = str(edge.get("label") or edge.get("description") or "").lower()
    if "done" in label or "completed" in label:
        return True
    return False


def _is_report_edge(edge: Dict[str, Any], role: str) -> bool:
    """Check whether a trace edge is a report mail from the role."""
    kind = str(edge.get("kind") or edge.get("type") or "").lower()
    if "mail" not in kind and "reply" not in kind:
        return False
    source = str(edge.get("source") or edge.get("from") or "")
    return role in source


def _check_acceptance_evidence(
    edges: List[Dict[str, Any]], handle: str, project: str
) -> Optional[str]:
    """Find an auditor verdict in the trace.

    Returns the verdict string if found, or None.
    Looks for a task-done edge with a verdict field or label mentioning
    clean_pass or residual.
    """
    for edge in edges:
        kind = str(edge.get("kind") or edge.get("type") or "").lower()
        label = str(edge.get("label") or edge.get("description") or "").lower()
        # Check for explicit verdict in edge data
        verdict = str(edge.get("verdict") or "").lower()
        if verdict in ("clean_pass", "residual"):
            return verdict
        # Check label for verdict mention
        if "clean_pass" in label:
            return "clean_pass"
        if "residual" in label:
            return "residual"
    return None


def _check_admission_evidence(
    edges: List[Dict[str, Any]], handle: str, project: str
) -> Dict[str, bool]:
    """Check for P2 and P3 audit receipts in the trace.

    Returns {"p2": bool, "p3": bool}.
    """
    found: Dict[str, bool] = {"p2": False, "p3": False}
    for edge in edges:
        label = str(edge.get("label") or edge.get("description") or "").lower()
        kind = str(edge.get("kind") or edge.get("type") or "").lower()
        # Look for goal-reality and delivery-reality audit indicators
        if "goal" in label and ("reality" in label or "audit" in label):
            found["p2"] = True
        if "delivery" in label and ("reality" in label or "audit" in label):
            found["p3"] = True
        # Also check for explicit pass references
        if "p2" in label or "p2" in kind:
            found["p2"] = True
        if "p3" in label or "p3" in kind:
            found["p3"] = True
    return found


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="fleet",
        description="Fleet chain gate: prepare → claim → settle → advance.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # prepare
    prep = sub.add_parser("prepare", help="Create assignment + frozen receipt")
    add_fleet_scope_arguments(prep, required_project=True)
    prep.add_argument("--to", dest="role_to", required=True, help="assignee role")
    prep.add_argument(
        "--pass", dest="pass_name", required=True,
        help="planning/execution pass (implement, review, goal-forge, delivery, p1, p2, p3)",
    )
    prep.add_argument("--scope", default=None, help="declared write scope")
    prep.add_argument("--subject", required=True, help="task subject")
    prep.add_argument("--body", default=None, help="task body")
    prep.add_argument("--body-file", default=None, help="read body from file")
    prep.add_argument(
        "--role-binding", dest="role_binding", default=None,
        help="explicit role binding override (provider/model/harness)",
    )
    prep.set_defaults(func=cmd_prepare)

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
    settle.add_argument("--verdict", default=None, help="audit verdict")
    settle.add_argument("--scope", default=None, help="declared scope")
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
    if not args.body and not args.body_file and args.command == "prepare":
        p.error("prepare requires --body or --body-file")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
