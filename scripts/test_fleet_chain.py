#!/usr/bin/env python3
"""Tests for the fleet chain gate (fleet.py).

Uses unittest with temp dirs and a mocked run_cmd so no live vivi binary
is required. Follows the pattern from test_fleet_common.py.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import fleet  # noqa: E402
import fleet_common  # noqa: E402


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class ViviMock:
    """Mock run_cmd that returns canned responses based on command patterns."""

    def __init__(self) -> None:
        self._patterns: List[Tuple[Tuple[str, ...], Tuple[int, str]]] = []

    def add(self, *pattern: str, rc: int = 0, output: str = "") -> "ViviMock":
        self._patterns.append((pattern, (rc, output)))
        return self

    def __call__(
        self,
        cmd: Sequence[str],
        timeout: float = 30.0,
        cwd: Any = None,
        env: Any = None,
    ) -> Tuple[int, str]:
        cmd_str = " ".join(str(c) for c in cmd)
        for pattern, (rc, output) in self._patterns:
            pat_str = " ".join(pattern)
            if pat_str in cmd_str:
                return rc, output
        return 127, "mock: command not configured for: %s" % cmd_str


def _task_json(
    handle: str = "task-abc",
    to: str = "hand-1",
    body: str = "test assignment body",
    status: str = "open",
    include_report: bool = True,
) -> str:
    role = "done" if status == "done" else "tasks"
    rows: List[Dict[str, Any]] = [
        {
            "handle": handle,
            "account": to,
            "role": role,
            "kind": "task",
            "to": "%s@test.local" % to,
            "body": body + "\r\n",
        }
    ]
    if status == "done" and include_report:
        rows.append(
            {
                "handle": "mail-1",
                "account": to,
                "role": "sent",
                "kind": "mail",
                "from": "%s@test.local" % to,
                "to": "mind@test.local",
                "body": "fleet-report:\r\ndurable report\r\n",
            }
        )
    return json.dumps(rows)


def _role_json(
    role: str = "hand-1",
    provider: str = "anthropic",
    model: str = "sonnet",
    harness: str = "subagent",
) -> str:
    return json.dumps(
        {"name": role, "provider": provider, "model": model, "harness": harness}
    )


def _trace_json(
    edges: List[Dict[str, Any]],
) -> str:
    has_report = any(str(edge.get("kind") or "") == "mail" for edge in edges)
    nodes: List[Dict[str, Any]] = [
        {
            "handle": "task-abc",
            "messages": [{"handle": "task-abc", "kind": "task", "role": "done"}],
        }
    ]
    if has_report:
        nodes.append(
            {
                "handle": "mail-1",
                "body": "fleet-report:\ndurable report",
                "messages": [
                    {
                        "handle": "mail-1",
                        "kind": "mail",
                        "from": "hand-1@test.local",
                        "to": "mind@test.local",
                    }
                ],
            }
        )
    return json.dumps({"seed": "task-abc", "nodes": nodes})


class CliParsingTests(unittest.TestCase):
    """Exercise live-shaped output parsing and top-level dispatch."""

    def test_parse_live_vivi_send_output_uses_recipient_copy(self) -> None:
        output = "created hand-1 3256f67d\nsent 93441a2b\n"
        self.assertEqual(
            fleet._parse_handle_from_send_output(output, "hand-1"),
            "3256f67d",
        )

    def test_main_dispatches_non_prepare_command(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            rc = fleet.main(
                ["claim", "--project", d, "missing", "--role", "hand-1"]
            )
        self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# Receipt round-trip
# ---------------------------------------------------------------------------


class ReceiptRoundTripTests(unittest.TestCase):
    """Test sidecar receipt I/O through fleet_common helpers."""

    def test_receipt_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            handle = "test-abc@mailspace"
            data: Dict[str, Any] = {
                "handle": handle,
                "role": "hand-1",
                "claim": None,
                "settlement": None,
            }
            fleet_common.save_receipt(d, handle, data)
            loaded = fleet_common.load_receipt(d, handle)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded["handle"], handle)
            self.assertEqual(loaded["role"], "hand-1")
            self.assertIsNone(loaded["claim"])

    def test_load_missing_receipt_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            result = fleet_common.load_receipt(d, "nonexistent")
            self.assertIsNone(result)

    def test_sanitize_handle(self) -> None:
        self.assertEqual(
            fleet_common.sanitize_handle("abc-123@safe"), "abc-123_safe"
        )
        self.assertEqual(fleet_common.sanitize_handle("clean-handle"), "clean-handle")

    def test_sha256_prefix(self) -> None:
        h = fleet_common.sha256_hex("test")
        self.assertTrue(h.startswith("sha256:"))
        self.assertEqual(len(h), 7 + 64)  # prefix + 64 hex chars


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------


class PrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_run_cmd = fleet.run_cmd

    def tearDown(self) -> None:
        fleet.run_cmd = self._orig_run_cmd

    def test_prepare_creates_receipt(self) -> None:
        body = "implement unit X"
        mock = ViviMock()
        mock.add("role", "show", "hand-1", output=_role_json())
        mock.add("task", "send", output="task-abc123")
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            args = fleet.parser().parse_args(
                [
                    "prepare", "--project", d,
                    "--to", "hand-1",
                    "--pass", "implement",
                    "--scope", "src/module/",
                    "--subject", "test unit",
                    "--body", body,
                ]
            )
            rc = fleet.cmd_prepare(args)
            self.assertEqual(rc, 0)

            receipt = fleet_common.load_receipt(d, "task-abc123")
            self.assertIsNotNone(receipt)
            assert receipt is not None
            self.assertEqual(receipt["handle"], "task-abc123")
            self.assertEqual(receipt["role"], "hand-1")
            self.assertEqual(receipt["pass"], "implement")
            self.assertEqual(receipt["scope"], "src/module/")
            self.assertIsNone(receipt["claim"])
            self.assertIsNone(receipt["settlement"])
            self.assertTrue(receipt["assignment_body_hash"].startswith("sha256:"))
            self.assertIn("task-abc123", receipt["boot_prompt"])
            # Hash must match the body
            self.assertEqual(
                receipt["assignment_body_hash"],
                fleet_common.sha256_hex(body),
            )
            self.assertEqual(receipt["expected_role_binding"]["model"], "sonnet")

    def test_prepare_boot_prompt(self) -> None:
        mock = ViviMock()
        mock.add("role", "show", "hand-1", output=_role_json())
        mock.add("task", "send", output="task-xyz")
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            args = fleet.parser().parse_args(
                [
                    "prepare", "--project", d,
                    "--to", "hand-1",
                    "--pass", "implement",
                    "--scope", "scripts/fleet.py",
                    "--subject", "test",
                    "--body", "body",
                ]
            )
            import io
            import contextlib

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = fleet.cmd_prepare(args)
            self.assertEqual(rc, 0)
            output = buf.getvalue()
            self.assertIn("claim", output)
            self.assertIn("task-xyz", output)
            self.assertIn("settle", output)

            prompt_args = fleet.parser().parse_args(
                ["prompt", "--project", d, "task-xyz"]
            )
            replay = io.StringIO()
            with contextlib.redirect_stdout(replay):
                rc = fleet.cmd_prompt(prompt_args)
            self.assertEqual(rc, 0)
            self.assertEqual(replay.getvalue(), output)

    def test_prepare_role_resolution_failure(self) -> None:
        mock = ViviMock()
        mock.add("role", "show", "unknown", rc=1, output="not found")
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            args = fleet.parser().parse_args(
                [
                    "prepare", "--project", d,
                    "--to", "unknown",
                    "--pass", "implement",
                    "--scope", "scripts/fleet.py",
                    "--subject", "test",
                    "--body", "body",
                ]
            )
            rc = fleet.cmd_prepare(args)
            self.assertEqual(rc, 1)

    def test_prepare_node_ready_records_graph_node(self) -> None:
        body = "do verify"
        show = json.dumps(
            {
                "graph": {"code": "wave", "handle": "gph_1"},
                "nodes": [
                    {
                        "source_id": "verify",
                        "state": "open",
                        "readiness": "ready",
                    }
                ],
            }
        )
        mock = ViviMock()
        mock.add("graph", "show", "wave", output=show)
        mock.add("role", "show", "hand-1", output=_role_json())
        mock.add("task", "send", output="task-node1")
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            args = fleet.parser().parse_args(
                [
                    "prepare", "--project", d,
                    "--to", "hand-1",
                    "--pass", "implement",
                    "--scope", "src/",
                    "--subject", "verify unit",
                    "--body", body,
                    "--node", "wave:verify",
                ]
            )
            rc = fleet.cmd_prepare(args)
            self.assertEqual(rc, 0)
            receipt = fleet_common.load_receipt(d, "task-node1")
            assert receipt is not None
            self.assertEqual(receipt["graph_node"], "wave:verify")

    def test_prepare_node_blocked_refuses(self) -> None:
        show = json.dumps(
            {
                "nodes": [
                    {
                        "source_id": "accept",
                        "state": "open",
                        "readiness": "blocked",
                        "blocked_by": ["verify"],
                    }
                ],
            }
        )
        mock = ViviMock()
        mock.add("graph", "show", "wave", output=show)
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            args = fleet.parser().parse_args(
                [
                    "prepare", "--project", d,
                    "--to", "hand-1",
                    "--pass", "implement",
                    "--scope", "src/",
                    "--subject", "accept",
                    "--body", "body",
                    "--node", "wave:accept",
                ]
            )
            rc = fleet.cmd_prepare(args)
            self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# claim
# ---------------------------------------------------------------------------


class ClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_run_cmd = fleet.run_cmd

    def tearDown(self) -> None:
        fleet.run_cmd = self._orig_run_cmd

    def _setup_receipt(
        self, project: str, handle: str = "task-abc", role: str = "hand-1",
        body: str = "test body",
    ) -> Dict[str, Any]:
        """Write a prepare receipt directly for test setup."""
        receipt: Dict[str, Any] = {
            "handle": handle,
            "kind": "task",
            "role": role,
            "scope": "src/",
            "pass": "implement",
            "expected_role_binding": {
                "provider": "anthropic",
                "model": "sonnet",
                "harness": "subagent",
            },
            "assignment_body_hash": fleet_common.sha256_hex(body),
            "prepared_at": "2026-01-01T00:00:00Z",
            "prepared_by": "mind",
            "claim": None,
            "settlement": None,
        }
        fleet_common.save_receipt(project, handle, receipt)
        return receipt

    def test_claim_succeeds(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add("role", "show", "hand-1", output=_role_json())
        mock.add("mail", "reply", output="mail-reply-1")
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_receipt(d, body=body)
            args = fleet.parser().parse_args(
                ["claim", "--project", d, "task-abc", "--role", "hand-1"]
            )
            rc = fleet.cmd_claim(args)
            self.assertEqual(rc, 0)

            receipt = fleet_common.load_receipt(d, "task-abc")
            assert receipt is not None
            self.assertIsNotNone(receipt["claim"])

    def test_claim_activates_graph_node(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add("role", "show", "hand-1", output=_role_json())
        mock.add("mail", "reply", output="mail-reply-1")
        mock.add("graph", "activate", "wave:verify", output="graph active")
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            receipt = self._setup_receipt(d, body=body)
            receipt["graph_node"] = "wave:verify"
            fleet_common.save_receipt(d, "task-abc", receipt)
            args = fleet.parser().parse_args(
                ["claim", "--project", d, "task-abc", "--role", "hand-1"]
            )
            rc = fleet.cmd_claim(args)
            self.assertEqual(rc, 0)
            loaded = fleet_common.load_receipt(d, "task-abc")
            assert loaded is not None
            self.assertIsNotNone(loaded["claim"])
            self.assertEqual(loaded["claim"]["role"], "hand-1")
            self.assertTrue(loaded["claim"]["binding_verified"])
            self.assertTrue(loaded["claim"].get("graph_activated"))

    def test_claim_idempotent(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add("role", "show", "hand-1", output=_role_json())
        mock.add("mail", "reply", output="mail-reply-1")
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_receipt(d, body=body)
            args = fleet.parser().parse_args(
                ["claim", "--project", d, "task-abc", "--role", "hand-1"]
            )
            # First claim
            rc = fleet.cmd_claim(args)
            self.assertEqual(rc, 0)
            # Second claim by same role
            rc = fleet.cmd_claim(args)
            self.assertEqual(rc, 0)

    def test_claim_wrong_role_fails(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(body=body, to="hand-1"))
        mock.add("role", "show", "hand-1", output=_role_json())
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_receipt(d, body=body)
            args = fleet.parser().parse_args(
                ["claim", "--project", d, "task-abc", "--role", "hand-2"]
            )
            rc = fleet.cmd_claim(args)
            self.assertEqual(rc, 1)

    def test_claim_hash_mismatch_fails(self) -> None:
        mock = ViviMock()
        # Task body differs from what prepare hashed
        mock.add("task", "show", "task-abc", output=_task_json(body="TAMPERED BODY"))
        mock.add("role", "show", "hand-1", output=_role_json())
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_receipt(d, body="original body")
            args = fleet.parser().parse_args(
                ["claim", "--project", d, "task-abc", "--role", "hand-1"]
            )
            rc = fleet.cmd_claim(args)
            self.assertEqual(rc, 1)

    def test_claim_missing_receipt_fails(self) -> None:
        mock = ViviMock()
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            args = fleet.parser().parse_args(
                ["claim", "--project", d, "nonexistent", "--role", "hand-1"]
            )
            rc = fleet.cmd_claim(args)
            self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# settle
# ---------------------------------------------------------------------------


class SettleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_run_cmd = fleet.run_cmd

    def tearDown(self) -> None:
        fleet.run_cmd = self._orig_run_cmd

    def _setup_claimed_receipt(
        self, project: str, handle: str = "task-abc", role: str = "hand-1",
    ) -> Dict[str, Any]:
        receipt: Dict[str, Any] = {
            "handle": handle,
            "kind": "task",
            "role": role,
            "scope": "src/",
            "pass": "implement",
            "expected_role_binding": {
                "provider": "anthropic",
                "model": "sonnet",
                "harness": "subagent",
            },
            "assignment_body_hash": fleet_common.sha256_hex("test body"),
            "prepared_at": "2026-01-01T00:00:00Z",
            "prepared_by": "mind",
            "claim": {
                "role": role,
                "claimed_at": "2026-01-01T00:01:00Z",
                "pid": 12345,
                "binding_verified": True,
            },
            "settlement": None,
        }
        fleet_common.save_receipt(project, handle, receipt)
        return receipt

    def test_settle_succeeds(self) -> None:
        mock = ViviMock()
        mock.add(
            "task", "show", "task-abc",
            output=_task_json(status="done"),
        )
        mock.add(
            "mail", "list",
            output=json.dumps([
                {
                    "handle": "mail-1",
                    "from": "hand-1",
                    "subject": "Re: task-abc",
                    "body": "done task-abc commit sha1",
                }
            ]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_claimed_receipt(d)
            args = fleet.parser().parse_args(
                [
                    "settle", "--project", d, "task-abc", "--role", "hand-1",
                    "--note", "done", "--report", "durable report",
                    "--repo", "examples", "--tip", "deadbee",
                ]
            )
            rc = fleet.cmd_settle(args)
            self.assertEqual(rc, 0)

            receipt = fleet_common.load_receipt(d, "task-abc")
            assert receipt is not None
            self.assertIsNotNone(receipt["settlement"])
            self.assertTrue(receipt["settlement"]["task_done_verified"])
            self.assertEqual(receipt["settlement"]["git_repo"], "examples")
            self.assertEqual(receipt["settlement"]["git_tip"], "deadbee")
            self.assertEqual(receipt["settlement"]["report_handle"], "mail-1")

    def test_settle_completes_task_and_creates_report(self) -> None:
        task_show_calls = 0

        def live_mock(
            cmd: Sequence[str],
            timeout: float = 30.0,
            cwd: Any = None,
            env: Any = None,
        ) -> Tuple[int, str]:
            nonlocal task_show_calls
            joined = " ".join(str(part) for part in cmd)
            if "task show task-abc" in joined:
                task_show_calls += 1
                if task_show_calls == 1:
                    return 0, _task_json(status="open")
                if task_show_calls == 2:
                    return 0, _task_json(status="done", include_report=False)
                return 0, _task_json(status="done")
            if "task done task-abc" in joined:
                return 0, "completed task-abc\n"
            if "mail reply task-abc" in joined:
                return 0, "replied mind mail-1\nsent mail-sender-1\n"
            return 127, "mock: command not configured for: %s" % joined

        fleet.run_cmd = live_mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_claimed_receipt(d)
            args = fleet.parser().parse_args(
                [
                    "settle", "--project", d, "task-abc", "--role", "hand-1",
                    "--note", "done", "--report", "durable report",
                    "--repo", "examples", "--tip", "deadbee",
                ]
            )
            rc = fleet.cmd_settle(args)
            self.assertEqual(rc, 0)
            receipt = fleet_common.load_receipt(d, "task-abc")
            assert receipt is not None
            self.assertEqual(receipt["settlement"]["report_handle"], "mail-1")
            self.assertEqual(task_show_calls, 3)

    def test_settle_double_fails(self) -> None:
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(status="done"))
        mock.add(
            "mail", "list",
            output=json.dumps([
                {
                    "handle": "mail-1",
                    "from": "hand-1",
                    "subject": "task-abc",
                    "body": "done",
                }
            ]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_claimed_receipt(d)
            args = fleet.parser().parse_args(
                [
                    "settle", "--project", d, "task-abc", "--role", "hand-1",
                    "--note", "done", "--report", "durable report",
                ]
            )
            # First settle
            rc = fleet.cmd_settle(args)
            self.assertEqual(rc, 0)
            # Second settle
            rc = fleet.cmd_settle(args)
            self.assertEqual(rc, 1)

    def test_settle_without_claim_fails(self) -> None:
        mock = ViviMock()
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            # Write receipt without claim
            receipt: Dict[str, Any] = {
                "handle": "task-abc",
                "role": "hand-1",
                "assignment_body_hash": fleet_common.sha256_hex("body"),
                "claim": None,
                "settlement": None,
            }
            fleet_common.save_receipt(d, "task-abc", receipt)
            args = fleet.parser().parse_args(
                [
                    "settle", "--project", d, "task-abc", "--role", "hand-1",
                    "--note", "done", "--report", "durable report",
                ]
            )
            rc = fleet.cmd_settle(args)
            self.assertEqual(rc, 1)

    def test_settle_task_not_done_fails(self) -> None:
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(status="open"))
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_claimed_receipt(d)
            args = fleet.parser().parse_args(
                [
                    "settle", "--project", d, "task-abc", "--role", "hand-1",
                    "--note", "done", "--report", "durable report",
                ]
            )
            rc = fleet.cmd_settle(args)
            self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# advance
# ---------------------------------------------------------------------------


class AdvanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_run_cmd = fleet.run_cmd

    def tearDown(self) -> None:
        fleet.run_cmd = self._orig_run_cmd

    def _setup_settled_receipt(
        self, project: str, handle: str = "task-abc", role: str = "auditor-1",
        body: str = "test body", pass_name: str = "review",
        verdict: str = "clean_pass", depends_on: Any = None,
    ) -> Dict[str, Any]:
        receipt: Dict[str, Any] = {
            "handle": handle,
            "kind": "task",
            "role": role,
            "scope": "src/",
            "pass": pass_name,
            "depends_on": list(depends_on or []),
            "expected_role_binding": {
                "provider": "anthropic",
                "model": "sonnet",
                "harness": "subagent",
            },
            "assignment_body_hash": fleet_common.sha256_hex(body),
            "prepared_at": "2026-01-01T00:00:00Z",
            "prepared_by": "mind",
            "claim": {
                "role": role,
                "claimed_at": "2026-01-01T00:01:00Z",
                "pid": 12345,
                "binding_verified": True,
            },
            "settlement": {
                "settled_at": "2026-01-01T00:05:00Z",
                "task_done_verified": True,
                "report_handle": "mail-1",
                "git_repo": "examples",
                "git_tip": "abc123",
                "verdict": verdict,
                "scope_declared": "src/",
            },
        }
        fleet_common.save_receipt(project, handle, receipt)
        return receipt

    def _setup_dependency(
        self, project: str, handle: str, pass_name: str,
        role: str = "hand-1", verdict: Any = None,
    ) -> None:
        self._setup_settled_receipt(
            project,
            handle=handle,
            role=role,
            pass_name=pass_name,
            verdict=verdict,
        )

    def test_advance_missing_claim_fails(self) -> None:
        mock = ViviMock()
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            # Receipt without claim
            receipt: Dict[str, Any] = {
                "handle": "task-abc",
                "role": "hand-1",
                "assignment_body_hash": fleet_common.sha256_hex("body"),
                "claim": None,
                "settlement": None,
            }
            fleet_common.save_receipt(d, "task-abc", receipt)
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "acceptance", "--handle", "task-abc",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 1)

    def test_advance_missing_settle_fails(self) -> None:
        mock = ViviMock()
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            # Receipt with claim but no settlement
            receipt: Dict[str, Any] = {
                "handle": "task-abc",
                "role": "hand-1",
                "assignment_body_hash": fleet_common.sha256_hex("body"),
                "claim": {
                    "role": "hand-1",
                    "claimed_at": "2026-01-01T00:01:00Z",
                    "pid": 12345,
                    "binding_verified": True,
                },
                "settlement": None,
            }
            fleet_common.save_receipt(d, "task-abc", receipt)
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "acceptance", "--handle", "task-abc",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 1)

    def test_advance_dependency_cycle_fails(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add(
            "task", "show", "task-abc",
            output=_task_json(body=body, to="auditor-1", status="done"),
        )
        mock.add(
            "task", "show", "task-impl",
            output=_task_json(handle="task-impl", body=body, status="done"),
        )
        mock.add(
            "trace", "task-abc",
            output=_trace_json([{"kind": "mail"}]),
        )
        mock.add(
            "trace", "task-impl",
            output=_trace_json([{"kind": "mail"}]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_settled_receipt(
                d, body=body, depends_on=["task-impl"]
            )
            self._setup_settled_receipt(
                d,
                handle="task-impl",
                role="hand-1",
                body=body,
                pass_name="implement",
                verdict=None,
                depends_on=["task-abc"],
            )
            result = fleet._check_chain(d, "task-abc", "acceptance")
            self.assertEqual(result["verdict"], "fail")
            self.assertIn("dependency cycle at task-abc", result["gaps"])

    def test_advance_hash_mismatch_fails(self) -> None:
        body = "original body"
        mock = ViviMock()
        # Task body differs from frozen hash
        mock.add(
            "task", "show", "task-abc",
            output=_task_json(body="TAMPERED"),
        )
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1"},
            ]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_settled_receipt(d, body=body)
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "acceptance", "--handle", "task-abc",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 1)

    def test_advance_acceptance_pass(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("role", "show", "auditor-1", output=_role_json(role="auditor-1"))
        mock.add("role", "show", "hand-1", output=_role_json())
        mock.add(
            "task", "show", "task-abc",
            output=_task_json(body=body, to="auditor-1", status="done"),
        )
        mock.add(
            "task", "show", "task-impl",
            output=_task_json(handle="task-impl", body=body, status="done"),
        )
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1", "target": "mind"},
                {"kind": "event-done", "verdict": "clean_pass"},
            ]),
        )
        mock.add(
            "trace", "task-impl",
            output=_trace_json([{"kind": "mail", "source": "hand-1"}]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_dependency(d, "task-impl", "implement")
            self._setup_settled_receipt(d, body=body, depends_on=["task-impl"])
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "acceptance", "--handle", "task-abc",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 0)

    def test_advance_acceptance_no_audit_fails(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1", "target": "mind"},
            ]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_settled_receipt(d, body=body, verdict="residual")
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "acceptance", "--handle", "task-abc",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 1)

    def test_advance_admission_pass(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("role", "show", "auditor-1", output=_role_json(role="auditor-1"))
        mock.add("role", "show", "planner-1", output=_role_json(role="planner-1"))
        mock.add(
            "task", "show", "task-abc",
            output=_task_json(body=body, to="auditor-1", status="done"),
        )
        mock.add(
            "task", "show", "task-p1",
            output=_task_json(
                handle="task-p1", body=body, to="planner-1", status="done"
            ),
        )
        mock.add(
            "task", "show", "task-plan-p2",
            output=_task_json(
                handle="task-plan-p2", body=body, to="planner-1", status="done"
            ),
        )
        mock.add(
            "task", "show", "task-goal-audit",
            output=_task_json(
                handle="task-goal-audit",
                body=body,
                to="auditor-1",
                status="done",
            ),
        )
        mock.add(
            "task", "show", "task-p3",
            output=_task_json(
                handle="task-p3", body=body, to="planner-1", status="done"
            ),
        )
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1", "target": "mind"},
                {"label": "goal-reality audit", "verdict": "clean_pass"},
                {"label": "delivery-reality audit", "verdict": "clean_pass"},
            ]),
        )
        mock.add(
            "trace", "task-p1",
            output=_trace_json([{"kind": "mail", "source": "planner-1"}]),
        )
        mock.add(
            "trace", "task-plan-p2",
            output=_trace_json([{"kind": "mail", "source": "planner-1"}]),
        )
        mock.add(
            "trace", "task-goal-audit",
            output=_trace_json([{"kind": "mail", "source": "auditor-1"}]),
        )
        mock.add(
            "trace", "task-p3",
            output=_trace_json([{"kind": "mail", "source": "planner-1"}]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_settled_receipt(
                d, handle="task-p1", role="planner-1", pass_name="p1",
                verdict=None,
            )
            self._setup_settled_receipt(
                d, handle="task-plan-p2", role="planner-1", pass_name="p2",
                verdict=None, depends_on=["task-p1"],
            )
            self._setup_settled_receipt(
                d, handle="task-goal-audit", role="auditor-1",
                pass_name="goal-audit", verdict="clean_pass",
                depends_on=["task-plan-p2"],
            )
            self._setup_settled_receipt(
                d, handle="task-p3", role="planner-1", pass_name="p3",
                verdict=None, depends_on=["task-goal-audit"],
            )
            self._setup_settled_receipt(
                d, body=body, pass_name="delivery-audit",
                depends_on=["task-p3", "task-goal-audit"],
            )
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "admission", "--handle", "task-abc",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 0)

    def test_advance_admission_missing_p3_fails(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1", "target": "mind"},
                {"label": "goal-reality audit", "verdict": "clean_pass"},
            ]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_settled_receipt(d, body=body, pass_name="goal-audit")
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "admission", "--handle", "task-abc",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 1)

    def test_advance_missing_receipt_fails(self) -> None:
        mock = ViviMock()
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "acceptance", "--handle", "nonexistent",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 1)

    def test_advance_json_output(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("role", "show", "auditor-1", output=_role_json(role="auditor-1"))
        mock.add("role", "show", "hand-1", output=_role_json())
        mock.add(
            "task", "show", "task-abc",
            output=_task_json(body=body, to="auditor-1", status="done"),
        )
        mock.add(
            "task", "show", "task-impl",
            output=_task_json(handle="task-impl", body=body, status="done"),
        )
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1", "target": "mind"},
                {"kind": "event-done", "verdict": "clean_pass"},
            ]),
        )
        mock.add(
            "trace", "task-impl",
            output=_trace_json([{"kind": "mail", "source": "hand-1"}]),
        )
        fleet.run_cmd = mock

        import io
        import contextlib

        with tempfile.TemporaryDirectory() as d:
            self._setup_dependency(d, "task-impl", "implement")
            self._setup_settled_receipt(d, body=body, depends_on=["task-impl"])
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "acceptance", "--handle", "task-abc",
                    "--json",
                ]
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 0)
            result = json.loads(buf.getvalue())
            self.assertEqual(result["verdict"], "pass")
            self.assertEqual(result["gate"], "acceptance")
            self.assertEqual(result["handle"], "task-abc")

    def test_advance_trace_failure_fails(self) -> None:
        body = "test body"
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add("trace", "task-abc", rc=1, output="trace error")
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_settled_receipt(d, body=body)
            args = fleet.parser().parse_args(
                [
                    "advance", "--project", d,
                    "--gate", "acceptance", "--handle", "task-abc",
                ]
            )
            rc = fleet.cmd_advance(args)
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
