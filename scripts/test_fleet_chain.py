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
) -> str:
    return json.dumps({"handle": handle, "to": to, "body": body, "status": status})


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
    return json.dumps(
        {"seed": "task-abc", "nodes": [], "edges": edges}
    )


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
                    "--subject", "test",
                    "--body", "body",
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
            self.assertEqual(receipt["claim"]["role"], "hand-1")
            self.assertTrue(receipt["claim"]["binding_verified"])

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

    def test_settle_double_fails(self) -> None:
        mock = ViviMock()
        mock.add("task", "show", "task-abc", output=_task_json(status="done"))
        mock.add(
            "mail", "list",
            output=json.dumps([
                {"handle": "mail-1", "from": "hand-1", "subject": "task-abc", "body": "done"}
            ]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_claimed_receipt(d)
            args = fleet.parser().parse_args(
                ["settle", "--project", d, "task-abc", "--role", "hand-1"]
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
                ["settle", "--project", d, "task-abc", "--role", "hand-1"]
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
                ["settle", "--project", d, "task-abc", "--role", "hand-1"]
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
        self, project: str, handle: str = "task-abc", role: str = "hand-1",
        body: str = "test body",
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
                "verdict": None,
                "scope_declared": "src/",
            },
        }
        fleet_common.save_receipt(project, handle, receipt)
        return receipt

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
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1", "target": "mind"},
                {"kind": "event-done", "verdict": "clean_pass"},
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
            self._setup_settled_receipt(d, body=body)
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
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1", "target": "mind"},
                {"label": "goal-reality audit", "verdict": "clean_pass"},
                {"label": "delivery-reality audit", "verdict": "clean_pass"},
            ]),
        )
        fleet.run_cmd = mock

        with tempfile.TemporaryDirectory() as d:
            self._setup_settled_receipt(d, body=body)
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
            self._setup_settled_receipt(d, body=body)
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
        mock.add("task", "show", "task-abc", output=_task_json(body=body))
        mock.add(
            "trace", "task-abc",
            output=_trace_json([
                {"kind": "event-done", "source": "task-abc"},
                {"kind": "mail", "source": "hand-1", "target": "mind"},
                {"kind": "event-done", "verdict": "clean_pass"},
            ]),
        )
        fleet.run_cmd = mock

        import io
        import contextlib

        with tempfile.TemporaryDirectory() as d:
            self._setup_settled_receipt(d, body=body)
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
