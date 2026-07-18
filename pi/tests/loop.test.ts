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

// Pi one-batch lifecycle (auditor-2 c9678a1e): a follow-up sent during a
// running cycle (sendUserMessage with deliverAs "followUp") drains inside the
// same agent run, and Pi emits a single agent_settled only after the whole
// queued batch drains. Several accepts during one run therefore share ONE
// settle. The boolean in-flight flag models "a Fleet batch is running"; a
// single settle clears it and arms the deadline from the final completion.
// These tests model that lifecycle by mirroring onAgentSettled, which only
// calls settle() while isInFlight(). They fail on the rejected per-message
// outstanding count model (4eb6826): one agent_settled can never drain N
// accepts, so that model strands the scheduler in-flight forever with no
// scheduled deadline.

test("one Pi agent_settled after a busy follow-up drains clears in-flight and rebases from final completion", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0); // deadline = 300, nothing in flight
  p.accept(100_000); // original Fleet cycle A accepted/running
  assert.equal(p.isInFlight(), true);
  assert.equal(p.getDeadlineMs(), undefined);
  // Trusted-mail/manual follow-up B accepted while A is still running (adapter
  // allowBusyFollowUp path). Pi queues it as a continuation inside A's run.
  p.accept(110_000);
  assert.equal(p.isInFlight(), true);
  assert.equal(p.getDeadlineMs(), undefined);
  // No intermediate agent_settled exists. After the whole batch drains Pi
  // emits ONE agent_settled; onAgentSettled calls settle once.
  if (p.isInFlight()) p.settle(200_000);
  assert.equal(p.isInFlight(), false);
  // Deadline is the final (batch) completion + interval, not an earlier one.
  assert.equal(p.getDeadlineMs(), 200_000 + INTERVAL_MS);
});

test("several busy follow-ups accepted during one run settle in a single Pi agent_settled", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0);
  p.accept(10_000); // A
  p.accept(20_000); // follow-up B
  p.accept(30_000); // follow-up C
  assert.equal(p.isInFlight(), true);
  assert.equal(p.getDeadlineMs(), undefined);
  // One final agent_settled after all three drain clears the whole batch.
  if (p.isInFlight()) p.settle(60_000);
  assert.equal(p.isInFlight(), false);
  assert.equal(p.getDeadlineMs(), 60_000 + INTERVAL_MS);
});

test("an extra unrelated agent_settled after the batch settled is a no-op", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0);
  p.accept(100_000);
  p.accept(110_000); // follow-up during A
  if (p.isInFlight()) p.settle(200_000); // batch drains; one agent_settled
  assert.equal(p.isInFlight(), false);
  const armed = p.getDeadlineMs();
  assert.equal(armed, 200_000 + INTERVAL_MS);
  // A later, unrelated agent_settled (e.g. a non-Fleet turn) arrives with
  // nothing in flight. onAgentSettled's isInFlight() guard skips settle, so the
  // already-armed deadline is untouched.
  if (p.isInFlight()) p.settle(500_000); // skipped
  assert.equal(p.isInFlight(), false);
  assert.equal(p.getDeadlineMs(), armed); // unchanged
});

test("cadence update during one in-flight batch rebases from the single batch completion", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0);
  p.accept(100_000);
  p.accept(110_000); // follow-up during A; whole batch in flight
  // Cadence change mid-batch must not strand the batch; it only changes the
  // interval and invalidates stale callbacks.
  p.update(120_000, 600);
  assert.equal(p.getIntervalSec(), 600);
  // One final agent_settled clears the batch and arms from final completion.
  if (p.isInFlight()) p.settle(200_000);
  assert.equal(p.isInFlight(), false);
  assert.equal(p.getDeadlineMs(), 200_000 + 600_000);
});

test("stop mid-batch, single agent_settled while stopped, then restart stays honest", () => {
  const p = new ScheduledDeadlinePolicy(INTERVAL);
  p.start(0);
  p.accept(100_000);
  p.accept(110_000); // follow-up during A; whole batch in flight
  // Operator stops the loop while a batch is still running.
  p.stop();
  assert.equal(p.isRunning(), false);
  assert.equal(p.isInFlight(), true); // outstanding batch preserved across stop
  assert.equal(p.getDeadlineMs(), undefined);
  // The in-flight batch's single agent_settled arrives while stopped; settle
  // clears in-flight but arms nothing while the loop is stopped.
  if (p.isInFlight()) p.settle(200_000);
  assert.equal(p.isInFlight(), false);
  assert.equal(p.getDeadlineMs(), undefined);
  // Restart later: fresh deadline from restart; in-flight stays clear.
  p.start(300_000);
  assert.equal(p.isRunning(), true);
  assert.equal(p.isInFlight(), false);
  assert.equal(p.getDeadlineMs(), 300_000 + INTERVAL_MS);
});
