export type LoopSnapshot = {
  signals?: string[];
  fingerprint?: Record<string, unknown>;
};

function actionableFingerprintEdge(key: string, previous: unknown, next: unknown): boolean {
  if (previous === next || next === null || next === undefined || next === false) return false;
  if (previous === null || previous === undefined || previous === false) return true;
  if (typeof previous === "number" && typeof next === "number") return next > previous;
  if (typeof previous !== "string" || typeof next !== "string" || previous === next) return false;
  return key.endsWith("_head") || key.endsWith("_mail_pending") || key.startsWith("next_handle_");
}

export function snapshotHasActionableChange(previous: LoopSnapshot | undefined, next: LoopSnapshot): boolean {
  if (!previous) return false;
  const previousSignals = new Set(previous.signals ?? []);
  if ((next.signals ?? []).some((signal) => !previousSignals.has(signal))) return true;
  const previousFingerprint = previous.fingerprint ?? {};
  return Object.entries(next.fingerprint ?? {}).some(([key, value]) =>
    actionableFingerprintEdge(key, previousFingerprint[key], value));
}

export function loopGenerationIsCurrent(loopRunning: boolean, current: number, callback: number): boolean {
  return loopRunning && current === callback;
}

/**
 * Generation-safe one-shot scheduled-deadline policy for the Pi-owned Fleet loop.
 *
 * Invariant: the configured interval is the minimum delay from the most
 * recently completed Fleet cycle to the next scheduled cycle, regardless of
 * whether the completed cycle originated from schedule, sensor change, trusted
 * mail, or manual/follow-up delivery.
 *
 * The policy is timer-free and deterministic. It tracks only the next
 * scheduled deadline (epoch ms), a running flag, an in-flight flag, a
 * generation counter, and the configured interval. The host adapter owns the
 * real setTimeout/clearTimeout handle and drives start/stop/update/accept/
 * settle/fire at the correct seams; the policy decides the deadline and whether
 * a scheduled fire may deliver. There is no repeating-interval path and no
 * origin-specific clock.
 *
 * Lifecycle truth (do not regress to per-message accounting): Pi delivers a
 * follow-up message (sendUserMessage with deliverAs "followUp") as a
 * continuation that drains inside the active agent run, and emits a single
 * agent_settled event only after the whole queued batch has drained. Several
 * accepts during one run therefore share one settle. The boolean in-flight
 * flag is intentional: it means "a Fleet batch is running", not "one specific
 * accepted message". Counting one outstanding per accept and consuming one per
 * settle strands the scheduler in-flight forever (one agent_settled can never
 * drain N accepts), so do not reintroduce outstanding-per-accept here.
 */
export class ScheduledDeadlinePolicy {
  private intervalMs: number;
  private running = false;
  private inFlight = false;
  private deadlineMs: number | undefined;
  private generation = 0;

  constructor(intervalSec: number) {
    this.intervalMs = intervalSec * 1000;
  }

  getIntervalSec(): number {
    return this.intervalMs / 1000;
  }

  isRunning(): boolean {
    return this.running;
  }

  isInFlight(): boolean {
    return this.inFlight;
  }

  getDeadlineMs(): number | undefined {
    return this.deadlineMs;
  }

  getGeneration(): number {
    return this.generation;
  }

  /**
   * Fresh start (or restart). Arms the first scheduled deadline at now+interval
   * and bumps generation so any stale scheduled callback is invalidated.
   * In-flight state is untouched; a loop start with a cycle still in flight
   * (e.g. a cadence restart) does not forget it.
   */
  start(nowMs: number, intervalSec: number = this.intervalMs / 1000): void {
    this.intervalMs = intervalSec * 1000;
    this.running = true;
    this.deadlineMs = nowMs + this.intervalMs;
    this.generation += 1;
  }

  /**
   * Full stop. Clears the scheduled deadline and bumps generation so in-flight
   * async scheduled callbacks cannot deliver. In-flight state is preserved so a
   * cycle accepted just before stop still settles correctly.
   */
  stop(): void {
    this.running = false;
    this.deadlineMs = undefined;
    this.generation += 1;
  }

  /**
   * Cadence change while running. Replaces the pending scheduled deadline with
   * now+newInterval and bumps generation; running and in-flight state are
   * preserved (an in-flight cycle is not forgotten across a cadence update).
   * A no-op when stopped.
   */
  update(nowMs: number, intervalSec: number): void {
    this.intervalMs = intervalSec * 1000;
    if (this.running) {
      this.deadlineMs = nowMs + this.intervalMs;
      this.generation += 1;
    }
  }

  /**
   * A cycle of any origin (schedule, sensor, trusted mail, manual/follow-up)
   * was accepted and is now in flight. Invalidate the pending scheduled
   * callback so a stale scheduled delivery cannot fire during or immediately
   * after this cycle. Pi coalesces follow-ups into one run, so several accepts
   * during a single run share one agent_settled; the next scheduled deadline
   * arms when that single settle fires (see settle).
   */
  accept(_nowMs: number): void {
    this.inFlight = true;
    this.deadlineMs = undefined;
  }

  /**
   * A Fleet cycle completed (agent settled). Records completion and arms the
   * next scheduled deadline at completion+interval, regardless of origin. This
   * is the rebase that makes the interval a minimum delay from the most recent
   * completed cycle rather than from loop start. Because Pi drains a whole
   * batch of accepted cycles (original + any follow-ups) before emitting one
   * agent_settled, a single settle clears the entire in-flight batch and arms
   * the deadline from that final completion. A non-Fleet settle (no cycle was
   * in flight) never reaches here: the host's onAgentSettled only calls this
   * while in flight, so an extra unrelated agent_settled is a no-op at the
   * adapter guard.
   */
  settle(nowMs: number): void {
    this.inFlight = false;
    if (this.running) this.deadlineMs = nowMs + this.intervalMs;
  }

  /**
   * The scheduled one-shot fired. Consumes the pending deadline. A delivery is
   * permitted only while running and not already in flight; a fire during an
   * in-flight cycle (defensive: the host clears the timer on accept) does not
   * deliver. Returns whether the host may deliver a scheduled cycle now.
   */
  fire(): boolean {
    this.deadlineMs = undefined;
    return this.running && !this.inFlight;
  }
}
