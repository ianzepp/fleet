import assert from "node:assert/strict";
import test from "node:test";
import {
  loopGenerationIsCurrent,
  ScheduledDeadlinePolicy,
  snapshotHasActionableChange,
} from "../lib/loop-policy.ts";

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

// ScheduledDeadlinePolicy: the configured interval is the minimum delay from
// the most recently completed Fleet cycle to the next scheduled cycle,
// regardless of origin (schedule, sensor change, trusted mail, manual/follow-up).
// All times below are epoch milliseconds.

const INTERVAL = 300;
const INTERVAL_MS = INTERVAL * 1000;

test("fresh start arms the first deadline at now+interval", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  assert.equal(p.isRunning(), false);
  p.start(0);
  assert.equal(p.isRunning(), true);
  assert.equal(p.isInFlight(), false);
  assert.equal(p.getDeadlineMs(), INTERVAL_MS);
});

test("scheduled fire delivers when running and idle, then consumes the deadline", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0);
  assert.equal(p.fire(), true);
  assert.equal(p.getDeadlineMs(), undefined);
});

test("sensor cycle completing shortly before old deadline postpones scheduled cycle by a full interval", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0); // deadline = 300
  assert.equal(p.getDeadlineMs(), INTERVAL_MS);
  // Poll at 290 detects a sensor change; the cycle is accepted, which must
  // invalidate the pending scheduled callback due at 300.
  p.accept(290_000);
  assert.equal(p.isInFlight(), true);
  assert.equal(p.getDeadlineMs(), undefined);
  // The cycle completes at 291, only 9s after the now-stale scheduled deadline.
  p.settle(291_000);
  // Next scheduled deadline is a full interval after completion, not 9s.
  assert.equal(p.getDeadlineMs(), 291_000 + INTERVAL_MS);
  assert.ok(p.getDeadlineMs()! - 291_000 >= INTERVAL_MS);
});

test("scheduled cycle completion also rebases normally", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0); // deadline = 300
  assert.equal(p.fire(), true); // scheduled deadline fires at 300
  assert.equal(p.getDeadlineMs(), undefined);
  p.accept(300_000); // scheduled cycle delivered (in flight)
  // Refresh + processing means the cycle settles shortly after the fire.
  p.settle(305_000);
  // Rebased from completion (305), not from a repeating 600 tick.
  assert.equal(p.getDeadlineMs(), 305_000 + INTERVAL_MS);
  assert.ok(p.getDeadlineMs()! - 305_000 >= INTERVAL_MS);
});

test("mail and manual/follow-up origins behave identically (same accept/settle seam)", () => {
  // Trusted-mail origin.
  const mail = new ScheduledDeadlinePolicy(INTERVAL);
  mail.start(0);
  mail.accept(50_000);
  assert.equal(mail.getDeadlineMs(), undefined);
  mail.settle(52_000);
  assert.equal(mail.getDeadlineMs(), 52_000 + INTERVAL_MS);
  assert.ok(mail.getDeadlineMs()! - 52_000 >= INTERVAL_MS);

  // Manual/follow-up origin: identical path, identical result.
  const manual = new ScheduledDeadlinePolicy(INTERVAL);
  manual.start(0);
  manual.accept(70_000);
  manual.settle(71_000);
  assert.equal(manual.getDeadlineMs(), 71_000 + INTERVAL_MS);
});

test("repeated polls do not move the deadline (no accept/settle)", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0);
  assert.equal(p.getDeadlineMs(), INTERVAL_MS);
  // The independent poll path never calls a policy mutator. Time advancing past
  // 60/120/180/240 must not shift the armed deadline.
  assert.equal(p.getDeadlineMs(), INTERVAL_MS);
  assert.equal(p.getDeadlineMs(), INTERVAL_MS);
});

test("stop and update invalidate stale scheduled callbacks via generation", () => {
  // stop()
  const stopped = new ScheduledDeadlinePolicy(INTERVAL);
  stopped.start(0);
  const gen0 = stopped.getGeneration();
  stopped.stop();
  assert.equal(stopped.isRunning(), false);
  assert.ok(stopped.getGeneration() > gen0);
  assert.equal(loopGenerationIsCurrent(stopped.isRunning(), stopped.getGeneration(), gen0), false);
  assert.equal(stopped.getDeadlineMs(), undefined);
  // A stale scheduled callback captured at gen0 cannot deliver after stop.
  assert.equal(stopped.fire(), false);

  // update() replaces the deadline and bumps generation; a callback captured at
  // the prior generation is invalidated.
  const updated = new ScheduledDeadlinePolicy(INTERVAL);
  updated.start(0);
  const ugen0 = updated.getGeneration();
  updated.update(100_000, 120); // cadence change at 100s to 120s
  assert.ok(updated.getGeneration() > ugen0);
  assert.equal(loopGenerationIsCurrent(updated.isRunning(), updated.getGeneration(), ugen0), false);
  assert.equal(updated.getDeadlineMs(), 100_000 + 120_000);
  assert.equal(updated.getIntervalSec(), 120);
});

test("busy/in-flight cycles cannot cause an immediate scheduled follow-up after settle", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0); // deadline = 300
  // A cycle is accepted just before the old scheduled deadline and stays
  // in flight well past it (a long cycle). The scheduled one-shot was
  // invalidated by accept, so nothing fires at 300.
  p.accept(295_000);
  assert.equal(p.getDeadlineMs(), undefined);
  // The long cycle settles at 400.
  p.settle(400_000);
  // The next scheduled cycle is a full interval after completion, not an
  // immediate follow-up carried over from the missed 300 deadline.
  assert.equal(p.getDeadlineMs(), 400_000 + INTERVAL_MS);
  assert.ok(p.getDeadlineMs()! - 400_000 >= INTERVAL_MS);

  // Defensive: if a scheduled fire ever occurs while in flight, it must not
  // deliver and must not starve the rebased successor (settle re-arms).
  const busy = new ScheduledDeadlinePolicy(INTERVAL);
  busy.start(0);
  busy.accept(100_000);
  assert.equal(busy.fire(), false);
  busy.settle(150_000);
  assert.equal(busy.getDeadlineMs(), 150_000 + INTERVAL_MS);
});
