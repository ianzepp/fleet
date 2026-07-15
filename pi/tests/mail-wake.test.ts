import assert from "node:assert/strict";
import test from "node:test";
import {
  applyMailWakeDispatchResults,
  clearMailWakeTimerHandle,
  MailWakeCapacityError,
  MailWakeDebouncer,
  mailWakeDueOnLoopStart,
  mailWakeEndpointPlan,
  parseTrustedMailWakePayload,
  selectMailWakeOwner,
  type FleetRef,
} from "../extensions/fleet";

const event = (ids: string[]) => ({
  kind: "trusted_mail" as const,
  account: "agent-proton",
  messageIds: ids,
  timestamp: "2026-07-15T16:00:00.000Z",
});

const fleet = (fleetId: string): FleetRef => ({ root: `/tmp/${fleetId}`, fleetId, fleetFile: `/tmp/${fleetId}/.vivi/fleet.json` });
const ids = (prefix: string, count: number) => Array.from({ length: count }, (_, index) => `${prefix}-${index}`);

const triggers = (cycles: ReturnType<MailWakeDebouncer["ingest"]>) => cycles.map((cycle) => cycle.trigger);

test("one trusted event produces one immediate leading cycle", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  assert.deepEqual(scheduler.ingest(event(["m1"]), 0), [{
    trigger: "leading",
    messageIds: ["m1"],
    count: 1,
  }]);
  assert.equal(scheduler.due(60_000), undefined);
});

test("two events inside quiet window produce immediate plus one trailing cycle", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  assert.deepEqual(triggers(scheduler.ingest(event(["m1"]), 0)), ["leading"]);
  assert.deepEqual(scheduler.ingest(event(["m2"]), 10_000), []);
  assert.equal(scheduler.due(69_999), undefined);
  assert.deepEqual(scheduler.due(70_000), {
    trigger: "trailing",
    messageIds: ["m2"],
    count: 1,
  });
});

test("repeated arrivals reset the quiet deadline", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m1"]), 0);
  scheduler.ingest(event(["m2"]), 10_000);
  scheduler.ingest(event(["m3"]), 50_000);
  assert.equal(scheduler.due(109_999), undefined);
  assert.deepEqual(scheduler.due(110_000)?.messageIds, ["m2", "m3"]);
});

test("duplicate message ids are deduplicated and do not retrigger", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  assert.equal(scheduler.ingest(event(["m1", "m1"]), 0)[0].count, 1);
  assert.deepEqual(scheduler.ingest(event(["m1"]), 10_000), []);
  assert.equal(scheduler.due(70_000), undefined);
});

test("exact boundary with no pending event starts a new leading cycle", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m1"]), 0);
  assert.deepEqual(scheduler.ingest(event(["m2"]), 60_000), [{
    trigger: "leading",
    messageIds: ["m2"],
    count: 1,
  }]);
});

test("exact boundary with pending event coalesces pending and arrival without loss", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m1"]), 0);
  scheduler.ingest(event(["m2"]), 10_000);
  assert.deepEqual(scheduler.ingest(event(["m3"]), 70_000), [
    { trigger: "trailing", messageIds: ["m2", "m3"], count: 2 },
  ]);
  assert.equal(scheduler.due(130_000), undefined);
});

test("after-deadline arrival before timer callback coalesces pending and arrival without loss", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m1"]), 0);
  scheduler.ingest(event(["m2"]), 10_000);
  assert.deepEqual(scheduler.ingest(event(["m3"]), 75_000), [
    { trigger: "trailing", messageIds: ["m2", "m3"], count: 2 },
  ]);
  assert.equal(scheduler.due(135_000), undefined);
});

test("restart restores pending state and emits at most one trailing cycle", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m1"]), 0);
  scheduler.ingest(event(["m2"]), 10_000);

  const restored = new MailWakeDebouncer(60_000, scheduler.snapshot());
  assert.deepEqual(restored.due(70_000), {
    trigger: "trailing",
    messageIds: ["m2"],
    count: 1,
  });
  assert.equal(restored.due(70_001), undefined);
  assert.deepEqual(restored.ingest(event(["m2"]), 80_000), []);
});


test("pending queue exactly full rejects one more ID without marking it seen", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m0"]), 0);
  const fullPending = ids("pending", 50);
  scheduler.ingest(event(fullPending), 10_000);
  assert.throws(() => scheduler.ingest(event(["extra"]), 20_000), /capacity exceeded/);
  assert.deepEqual(scheduler.due(70_000), { trigger: "trailing", messageIds: fullPending, count: 50 });
  assert.deepEqual(scheduler.ingest(event(["extra"]), 70_001), [{ trigger: "leading", messageIds: ["extra"], count: 1 }]);
});


test("follow-up burst over capacity rejects all new IDs before marking them seen", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m0"]), 0);
  const pending = ids("pending", 49);
  const overflow = ["extra-1", "extra-2"];
  scheduler.ingest(event(pending), 10_000);
  assert.throws(() => scheduler.ingest(event(overflow), 20_000), (error) =>
    error instanceof MailWakeCapacityError && error.retryable && /capacity exceeded/.test(error.message));
  assert.deepEqual(scheduler.due(70_000), { trigger: "trailing", messageIds: pending, count: 49 });
  assert.deepEqual(scheduler.ingest(event(overflow), 70_001), [{ trigger: "leading", messageIds: overflow, count: 2 }]);
});


test("boundary pending plus arrival over capacity rejects arrival and preserves pending", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m0"]), 0);
  const fullPending = ids("pending", 50);
  scheduler.ingest(event(fullPending), 10_000);
  assert.throws(() => scheduler.ingest(event(["extra"]), 70_000), /capacity exceeded/);
  assert.deepEqual(scheduler.due(70_000), { trigger: "trailing", messageIds: fullPending, count: 50 });
  assert.deepEqual(scheduler.ingest(event(["extra"]), 70_001), [{ trigger: "leading", messageIds: ["extra"], count: 1 }]);
});


test("boundary pending plus burst over capacity rejects all arrivals before marking them seen", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m0"]), 0);
  const pending = ids("pending", 49);
  const overflow = ["extra-1", "extra-2"];
  scheduler.ingest(event(pending), 10_000);
  assert.throws(() => scheduler.ingest(event(overflow), 70_000), /capacity exceeded/);
  assert.deepEqual(scheduler.due(70_000), { trigger: "trailing", messageIds: pending, count: 49 });
  assert.deepEqual(scheduler.ingest(event(overflow), 70_001), [{ trigger: "leading", messageIds: overflow, count: 2 }]);
});

test("failed dispatch returns visible rejection and retains pending ids for retry", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  const cycles = scheduler.ingest(event(["m1"]), 0);
  const result = applyMailWakeDispatchResults(scheduler, cycles, () => false, 5_000);
  assert.equal(result.ok, false);
  assert.equal(result.accepted, false);
  assert.match(result.error ?? "", /retry/);
  assert.equal(scheduler.due(64_999), undefined);
  assert.deepEqual(scheduler.due(65_000), { trigger: "trailing", messageIds: ["m1"], count: 1 });
  assert.equal(scheduler.due(65_001), undefined);
});


test("accepted dispatch clears pending retry metadata", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  const cycles = scheduler.ingest(event(["m1"]), 0);
  const result = applyMailWakeDispatchResults(scheduler, cycles, () => true, 0);
  assert.equal(result.ok, true);
  assert.equal(scheduler.due(60_000), undefined);
});


test("failed dispatch retention preserves a max-sized cycle and rejects overflow until drained", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  const batch = ids("batch", 50);
  const cycles = scheduler.ingest(event(batch), 0);
  const result = applyMailWakeDispatchResults(scheduler, cycles, () => false, 1_000);
  assert.equal(result.ok, false);
  assert.throws(() => scheduler.ingest(event(["extra"]), 2_000), /capacity exceeded/);
  assert.deepEqual(scheduler.due(61_000), { trigger: "trailing", messageIds: batch, count: 50 });
  assert.deepEqual(scheduler.ingest(event(["extra"]), 61_001), [{ trigger: "leading", messageIds: ["extra"], count: 1 }]);
});


test("failed dispatch of an oversized cycle is rejected visibly and never truncated", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  const oversized = { trigger: "trailing" as const, messageIds: ids("oversized", 51), count: 51 };
  const result = applyMailWakeDispatchResults(scheduler, [oversized], () => false, 1_000);
  assert.equal(result.ok, false);
  assert.equal(result.retryable, true);
  assert.match(result.error ?? "", /capacity exceeded/);
  assert.deepEqual(scheduler.snapshot().pendingIds, []);
  assert.equal(scheduler.due(61_000), undefined);
});


test("restart with pending state and unavailable loop preserves pending metadata", () => {
  const scheduler = new MailWakeDebouncer(60_000);
  scheduler.ingest(event(["m1"]), 0);
  scheduler.ingest(event(["m2"]), 10_000);
  const restored = new MailWakeDebouncer(60_000, scheduler.snapshot());
  assert.equal(mailWakeDueOnLoopStart(false, restored, 70_000), undefined);
  assert.deepEqual(restored.snapshot().pendingIds, ["m2"]);
  assert.deepEqual(mailWakeDueOnLoopStart(true, restored, 70_000), { trigger: "trailing", messageIds: ["m2"], count: 1 });
});

test("mail wake endpoint is disabled without an active loop and is Ops-capability scoped", () => {
  const ops = fleet("ops");
  const generic = fleet("generic");
  const config = (item: FleetRef) => item.fleetId === "ops" ? { ops_bridge: { account: "agent-proton" } } : {};
  assert.deepEqual(mailWakeEndpointPlan(false, [ops], config), {});
  assert.deepEqual(mailWakeEndpointPlan(true, [generic], config), {});
  assert.equal(mailWakeEndpointPlan(true, [generic, ops], config).fleet, ops);
});

test("multiple Ops-capable owners are refused as ambiguous", () => {
  const first = fleet("ops-a");
  const second = fleet("ops-b");
  const result = selectMailWakeOwner([first, second], () => ({ ops_bridge: {} }));
  assert.equal(result.fleet, undefined);
  assert.match(result.error ?? "", /multiple Ops-capable/);
});

test("clearing the mail wake timer prevents stopped-loop trailing callbacks", async () => {
  let fired = false;
  const timer = setTimeout(() => {
    fired = true;
  }, 5);
  clearMailWakeTimerHandle(timer);
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(fired, false);
});

test("malformed, oversized, body-bearing, and unused wire fields are rejected", () => {
  assert.throws(() => parseTrustedMailWakePayload({ kind: "trusted_mail", account: "agent-proton", message_ids: ["m1"], count: 1, timestamp: "bad" }));
  assert.throws(() => parseTrustedMailWakePayload({ kind: "trusted_mail", account: "agent-proton", message_ids: ["x".repeat(161)], count: 1, timestamp: "2026-07-15T16:00:00Z" }));
  assert.throws(() => parseTrustedMailWakePayload({ kind: "trusted_mail", account: "agent-proton", message_ids: ["m1"], count: 1, timestamp: "2026-07-15T16:00:00Z", body: "nope" }));
  assert.throws(() => parseTrustedMailWakePayload({ kind: "trusted_mail", account: "agent-proton", message_ids: ["m1"], count: 1, timestamp: "2026-07-15T16:00:00Z", subject: "prompt" }));
  assert.throws(() => parseTrustedMailWakePayload({ kind: "trusted_mail", account: "agent-proton", message_ids: ["m1"], count: 1, timestamp: "2026-07-15T16:00:00Z", event_id: "unused" }));
});

test("valid wire payload normalizes duplicate ids without accepting bodies", () => {
  assert.deepEqual(parseTrustedMailWakePayload({
    kind: "trusted_mail",
    account: "agent-proton",
    message_ids: ["m1", "m1", "m2"],
    count: 2,
    timestamp: "2026-07-15T16:00:00Z",
  }).messageIds, ["m1", "m2"]);
});
