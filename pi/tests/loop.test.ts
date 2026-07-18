import assert from "node:assert/strict";
import test from "node:test";
import {
  loopGenerationIsCurrent,
  snapshotHasActionableChange,
} from "../extensions/loop-policy.ts";

const snapshot = (signals: string[] = [], fingerprint: Record<string, unknown> = {}) => ({
  signals,
  fingerprint,
});

test("sensor wake ignores signal removal and unchanged actionable state", () => {
  const previous = snapshot(["mail_for_hand-1", "wake_candidate_hand-1"], {
    hand1_open: 1,
    next_handle_h1: "task-1",
  });
  const next = snapshot(["wake_candidate_hand-1"], {
    hand1_open: 1,
    next_handle_h1: "task-1",
  });

  assert.equal(snapshotHasActionableChange(previous, next), false);
});

test("sensor wake fires for a newly added obligation", () => {
  const previous = snapshot(["wake_candidate_hand-1"]);
  const next = snapshot(["wake_candidate_hand-1", "runtime_hand-1_failed"]);

  assert.equal(snapshotHasActionableChange(previous, next), true);
});

test("sensor wake fires for new work and changed git tips but not work removal", () => {
  assert.equal(snapshotHasActionableChange(
    snapshot([], { hand1_open: 0 }),
    snapshot([], { hand1_open: 1 }),
  ), true);
  assert.equal(snapshotHasActionableChange(
    snapshot([], { hand1_open: 1 }),
    snapshot([], { hand1_open: 0 }),
  ), false);
  assert.equal(snapshotHasActionableChange(
    snapshot([], { swarm_head: "abc" }),
    snapshot([], { swarm_head: "def" }),
  ), true);
});

test("sensor wake ignores runtime chrome transitions without a new signal", () => {
  assert.equal(snapshotHasActionableChange(
    snapshot([], { hand1_state: "waiting_for_input" }),
    snapshot([], { hand1_state: "running" }),
  ), false);
});

test("superseded and stopped timer generations cannot deliver", () => {
  assert.equal(loopGenerationIsCurrent(true, 3, 3), true);
  assert.equal(loopGenerationIsCurrent(true, 4, 3), false);
  assert.equal(loopGenerationIsCurrent(false, 3, 3), false);
});
