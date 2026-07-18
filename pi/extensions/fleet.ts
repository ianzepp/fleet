import { chmodSync, existsSync, readFileSync, statSync, unlinkSync } from "node:fs";
import { createServer } from "node:net";
import type { Server, Socket } from "node:net";
import { hostname } from "node:os";
import { dirname, resolve } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";
import { Type } from "typebox";
import { loopGenerationIsCurrent, ScheduledDeadlinePolicy, snapshotHasActionableChange } from "../lib/loop-policy";

const FLEET_ROOT = resolve(dirname(__dirname), "..");
const SCRIPTS = resolve(FLEET_ROOT, "scripts");
const SENSOR_SCRIPT = resolve(SCRIPTS, "fleet-sensors.py");
const BASELINE_SCRIPT = resolve(SCRIPTS, "fleet-baseline.py");
const LOOP_SCRIPT = resolve(SCRIPTS, "fleet-loop.py");
const VERIFY_SCRIPT = resolve(SCRIPTS, "verify-fleet-json.py");
const STEWARD_SCRIPT = resolve(SCRIPTS, "steward.sh");

const DEFAULT_INTERVAL_SEC = 300;
const MIN_INTERVAL_SEC = 60;
const POLL_INTERVAL_MS = 60_000;
const ATTACHMENT_ENTRY = "pi-fleet-attachment";
const MONITOR_ENTRY = "pi-fleet-monitor";
const VIEW_ENTRY = "pi-fleet-view";
const LOOP_ENTRY = "pi-fleet-loop";
const MAIL_WAKE_ENTRY = "pi-fleet-mail-wake";
const MAIL_WAKE_SOCKET = "pi-fleet-wake.sock";
const MAIL_WAKE_QUIET_MS = 60_000;
const MAIL_WAKE_MAX_IDS = 50;
const MAIL_WAKE_MAX_ID_LEN = 160;
const MAIL_WAKE_MAX_ACCOUNT_LEN = 128;
const MAIL_WAKE_MAX_LINE = 8192;
const MAIL_WAKE_SEEN_LIMIT = 500;
const WIDGET_KEY = "pi-fleet";
const STATUS_KEY = "pi-fleet";

type JsonObject = Record<string, unknown>;

export type FleetRef = {
  root: string;
  fleetId: string;
  fleetFile: string;
};

type Snapshot = JsonObject & {
  fleet_id?: string;
  fleet_posture?: { mode?: string };
  signals?: string[];
  fingerprint?: JsonObject;
  hands?: Record<string, JsonObject>;
  heads?: Record<string, JsonObject>;
  operator?: JsonObject;
  mind?: JsonObject;
  integration?: JsonObject;
  steward?: JsonObject;
  runtime?: JsonObject;
  partial?: boolean;
};

type ExternalLoop = {
  running?: boolean;
  state?: JsonObject;
};

type AttachmentEntry = {
  action: "attach" | "detach";
  root: string;
  fleetId: string;
};

type MonitorEntry = {
  action: "attach" | "detach";
  root: string;
  fleetId: string;
};

type MonitorEvent = {
  cycle: number;
  at?: string;
  acted: boolean;
  summary: string;
  signalCount: number;
};

type FleetViewMode = "compact" | "expanded" | "focus";

type ViewEntry = {
  mode: FleetViewMode;
  fleetId?: string;
};

type LoopEntry = {
  running: boolean;
  intervalSec: number;
};

type MailWakeStateEntry = {
  version: 1;
  seenIds: string[];
  windowDeadlineAt?: string;
  pendingIds: string[];
};

export type TrustedMailWakeEvent = {
  kind: "trusted_mail";
  account: string;
  messageIds: string[];
  timestamp: string;
};

export type MailWakeCycle = {
  trigger: "leading" | "trailing" | "retry";
  messageIds: string[];
  count: number;
};

export type MailWakeSnapshot = {
  seenIds: string[];
  windowDeadlineMs?: number;
  pendingIds: string[];
};

export class MailWakeCapacityError extends Error {
  readonly retryable = true;

  constructor(message: string) {
    super(message);
    this.name = "MailWakeCapacityError";
  }
}

export class MailWakeDebouncer {
  private readonly seenIds: string[];
  private readonly seenSet: Set<string>;
  private readonly pendingIds: string[];
  private readonly pendingSet: Set<string>;
  private windowDeadlineMs?: number;

  constructor(
    private readonly quietMs = MAIL_WAKE_QUIET_MS,
    snapshot?: MailWakeSnapshot,
    private readonly seenLimit = MAIL_WAKE_SEEN_LIMIT,
  ) {
    this.seenIds = [];
    this.seenSet = new Set();
    this.pendingIds = [];
    this.pendingSet = new Set();
    for (const id of snapshot?.seenIds ?? []) this.rememberSeen(id);
    this.windowDeadlineMs = snapshot?.windowDeadlineMs;
    this.assertPendingCapacity(snapshot?.pendingIds ?? []);
    for (const id of snapshot?.pendingIds ?? []) this.rememberPending(id);
  }

  ingest(event: TrustedMailWakeEvent, nowMs: number): MailWakeCycle[] {
    const newIds: string[] = [];
    const eventSeen = new Set<string>();
    for (const id of event.messageIds) {
      if (eventSeen.has(id) || this.seenSet.has(id)) continue;
      eventSeen.add(id);
      newIds.push(id);
    }
    if (newIds.length === 0) return [];
    if (newIds.length > MAIL_WAKE_MAX_IDS) {
      throw new MailWakeCapacityError(`mail wake event capacity exceeded: max ${MAIL_WAKE_MAX_IDS} message IDs`);
    }
    if (this.windowDeadlineMs !== undefined) this.assertPendingCapacity(newIds);
    for (const id of newIds) this.rememberSeen(id);
    if (this.windowDeadlineMs === undefined) {
      this.windowDeadlineMs = nowMs + this.quietMs;
      return [{ trigger: "leading", messageIds: newIds, count: newIds.length }];
    }
    if (nowMs >= this.windowDeadlineMs) {
      const duePending = [...this.pendingIds];
      this.pendingIds.length = 0;
      this.pendingSet.clear();
      this.windowDeadlineMs = nowMs + this.quietMs;
      const messageIds = [...duePending, ...newIds];
      return [{ trigger: duePending.length > 0 ? "trailing" : "leading", messageIds, count: messageIds.length }];
    }
    for (const id of newIds) this.rememberPending(id);
    this.windowDeadlineMs = nowMs + this.quietMs;
    return [];
  }

  retainForRetry(cycle: MailWakeCycle, nowMs: number): void {
    this.assertPendingCapacity(cycle.messageIds);
    for (const id of cycle.messageIds) this.rememberPending(id);
    if (this.pendingIds.length > 0) this.windowDeadlineMs = nowMs + this.quietMs;
  }

  due(nowMs: number): MailWakeCycle | undefined {
    if (this.windowDeadlineMs === undefined || nowMs < this.windowDeadlineMs) return undefined;
    this.windowDeadlineMs = undefined;
    if (this.pendingIds.length === 0) return undefined;
    const messageIds = [...this.pendingIds];
    this.pendingIds.length = 0;
    this.pendingSet.clear();
    return { trigger: "trailing", messageIds, count: messageIds.length };
  }

  nextDeadlineMs(): number | undefined {
    return this.windowDeadlineMs;
  }

  snapshot(): MailWakeSnapshot {
    return {
      seenIds: [...this.seenIds],
      windowDeadlineMs: this.windowDeadlineMs,
      pendingIds: [...this.pendingIds],
    };
  }

  private rememberSeen(id: string): void {
    if (this.seenSet.has(id)) return;
    this.seenSet.add(id);
    this.seenIds.push(id);
    while (this.seenIds.length > this.seenLimit) {
      const removed = this.seenIds.shift();
      if (removed) this.seenSet.delete(removed);
    }
  }

  private assertPendingCapacity(ids: string[]): void {
    const additional = ids.filter((id) => !this.pendingSet.has(id));
    if (this.pendingIds.length + additional.length > MAIL_WAKE_MAX_IDS) {
      throw new MailWakeCapacityError(`mail wake pending capacity exceeded: max ${MAIL_WAKE_MAX_IDS} message IDs`);
    }
  }

  private rememberPending(id: string): void {
    if (this.pendingSet.has(id)) return;
    this.pendingSet.add(id);
    this.pendingIds.push(id);
  }
}

export function applyMailWakeDispatchResults(
  debouncer: MailWakeDebouncer,
  cycles: MailWakeCycle[],
  dispatch: (cycle: MailWakeCycle) => boolean,
  nowMs: number,
): { ok: boolean; accepted: boolean; new_cycles: string[]; error?: string; retryable?: boolean } {
  let accepted = true;
  let error: string | undefined;
  let retryable: boolean | undefined;
  for (const cycle of cycles) {
    if (dispatch(cycle)) continue;
    try {
      debouncer.retainForRetry(cycle, nowMs);
      error = "trusted mail wake queued for retry; active Fleet cycle was unavailable";
      retryable = true;
    } catch (caught) {
      error = caught instanceof Error ? caught.message : String(caught);
      retryable = caught instanceof MailWakeCapacityError ? caught.retryable : undefined;
    }
    accepted = false;
  }
  return {
    ok: accepted,
    accepted,
    new_cycles: cycles.map((cycle) => cycle.trigger),
    error,
    retryable,
  };
}

export function mailWakeDueOnLoopStart(loopRunning: boolean, debouncer: MailWakeDebouncer, nowMs: number): MailWakeCycle | undefined {
  return loopRunning ? debouncer.due(nowMs) : undefined;
}

function hasForbiddenMailWakeKey(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  if (Array.isArray(value)) return value.some(hasForbiddenMailWakeKey);
  for (const [key, child] of Object.entries(value as JsonObject)) {
    const normalized = key.toLowerCase();
    if (["body", "body_text", "body_html", "html", "text", "content", "snippet", "preview", "subject"].includes(normalized)) return true;
    if (hasForbiddenMailWakeKey(child)) return true;
  }
  return false;
}

function validWakeToken(value: unknown, maxLen: number): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= maxLen && !/[\s\x00-\x1f\x7f]/.test(value);
}

export function parseTrustedMailWakePayload(value: unknown): TrustedMailWakeEvent {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("mail wake event must be a JSON object");
  if (hasForbiddenMailWakeKey(value)) throw new Error("mail wake event must not include message body or prompt fields");
  const raw = value as JsonObject;
  const allowed = new Set(["kind", "account", "message_ids", "messageIds", "count", "timestamp"]);
  for (const key of Object.keys(raw)) {
    if (!allowed.has(key)) throw new Error(`unsupported mail wake field: ${key}`);
  }
  if (raw.kind !== "trusted_mail") throw new Error("mail wake event kind must be trusted_mail");
  if (!validWakeToken(raw.account, MAIL_WAKE_MAX_ACCOUNT_LEN)) throw new Error("invalid mail wake account");
  const rawIds = raw.message_ids ?? raw.messageIds;
  if (!Array.isArray(rawIds) || rawIds.length === 0 || rawIds.length > MAIL_WAKE_MAX_IDS) throw new Error("invalid mail wake message_ids");
  const messageIds: string[] = [];
  const seen = new Set<string>();
  for (const id of rawIds) {
    if (!validWakeToken(id, MAIL_WAKE_MAX_ID_LEN)) throw new Error("invalid mail wake message_id");
    if (!seen.has(id)) {
      seen.add(id);
      messageIds.push(id);
    }
  }
  if (typeof raw.count !== "number" || !Number.isInteger(raw.count) || raw.count < messageIds.length || raw.count > MAIL_WAKE_MAX_IDS) {
    throw new Error("invalid mail wake count");
  }
  if (typeof raw.timestamp !== "string" || !Number.isFinite(Date.parse(raw.timestamp))) throw new Error("invalid mail wake timestamp");
  return { kind: "trusted_mail", account: raw.account, messageIds, timestamp: raw.timestamp };
}

function mailWakeEntryFromSnapshot(snapshot: MailWakeSnapshot): MailWakeStateEntry {
  return {
    version: 1,
    seenIds: snapshot.seenIds.slice(-MAIL_WAKE_SEEN_LIMIT),
    windowDeadlineAt: snapshot.windowDeadlineMs === undefined ? undefined : new Date(snapshot.windowDeadlineMs).toISOString(),
    pendingIds: snapshot.pendingIds.slice(0, MAIL_WAKE_MAX_IDS),
  };
}

function mailWakeSnapshotFromEntry(entry: Partial<MailWakeStateEntry> | undefined): MailWakeSnapshot | undefined {
  if (entry?.version !== 1 || !Array.isArray(entry.seenIds) || !Array.isArray(entry.pendingIds)) return undefined;
  const seenIds = entry.seenIds.filter((id) => validWakeToken(id, MAIL_WAKE_MAX_ID_LEN)).slice(-MAIL_WAKE_SEEN_LIMIT);
  const pendingIds = entry.pendingIds.filter((id) => validWakeToken(id, MAIL_WAKE_MAX_ID_LEN)).slice(0, MAIL_WAKE_MAX_IDS);
  const deadline = typeof entry.windowDeadlineAt === "string" ? Date.parse(entry.windowDeadlineAt) : undefined;
  return { seenIds, pendingIds, windowDeadlineMs: Number.isFinite(deadline) ? deadline : undefined };
}

type State = {
  ctx?: ExtensionContext;
  candidate?: FleetRef;
  attachments: Map<string, FleetRef>;
  monitors: Map<string, FleetRef>;
  snapshots: Map<string, Snapshot>;
  baselines: Map<string, JsonObject>;
  monitorSnapshots: Map<string, Snapshot>;
  monitorBaselines: Map<string, JsonObject>;
  monitorEvents: Map<string, MonitorEvent>;
  externalLoops: Map<string, ExternalLoop>;
  pollTimer?: ReturnType<typeof setInterval>;
  monitorTimer?: ReturnType<typeof setInterval>;
  loopTimer?: ReturnType<typeof setTimeout>;
  uiTimer?: ReturnType<typeof setInterval>;
  mailWakeTimer?: ReturnType<typeof setTimeout>;
  mailWakeSockets: Map<string, Server>;
  mailWakeDebouncer: MailWakeDebouncer;
  scheduler: ScheduledDeadlinePolicy;
  pollInFlight: boolean;
  cycleQueued: boolean;
  monitorIntervalSec: number;
  viewMode: FleetViewMode;
  focusedFleetId?: string;
  startedAt?: string;
  lastCycleAt?: string;
  lastPollAt?: string;
  lastError?: string;
};

const state: State = {
  attachments: new Map(),
  monitors: new Map(),
  snapshots: new Map(),
  baselines: new Map(),
  monitorSnapshots: new Map(),
  monitorBaselines: new Map(),
  monitorEvents: new Map(),
  externalLoops: new Map(),
  mailWakeSockets: new Map(),
  mailWakeDebouncer: new MailWakeDebouncer(),
  scheduler: new ScheduledDeadlinePolicy(DEFAULT_INTERVAL_SEC),
  pollInFlight: false,
  cycleQueued: false,
  monitorIntervalSec: 60,
  viewMode: "expanded",
};

function jsonFile(path: string): JsonObject | undefined {
  try {
    const value = JSON.parse(readFileSync(path, "utf8"));
    return value && typeof value === "object" && !Array.isArray(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

function fleetIdOf(config: JsonObject, root: string): string {
  for (const key of ["fleet_id", "mailspace"]) {
    const value = config[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return resolve(root).split(/[\\/]/).filter(Boolean).pop() ?? "fleet";
}

export function fleetConfigHasMailWakeCapability(config: Record<string, unknown> | undefined): boolean {
  const bridge = config?.ops_bridge;
  return !!bridge && typeof bridge === "object" && !Array.isArray(bridge);
}

export function selectMailWakeOwner(
  fleets: FleetRef[],
  configForFleet: (fleet: FleetRef) => Record<string, unknown> | undefined,
): { fleet?: FleetRef; error?: string } {
  const capable = fleets.filter((fleet) => fleetConfigHasMailWakeCapability(configForFleet(fleet)));
  if (capable.length === 0) return {};
  if (capable.length === 1) return { fleet: capable[0] };
  return { error: `multiple Ops-capable Fleet wake owners attached: ${capable.map((fleet) => fleet.fleetId).join(", ")}` };
}

export function mailWakeEndpointPlan(
  loopRunning: boolean,
  fleets: FleetRef[],
  configForFleet: (fleet: FleetRef) => Record<string, unknown> | undefined,
): { fleet?: FleetRef; error?: string } {
  if (!loopRunning) return {};
  return selectMailWakeOwner(fleets, configForFleet);
}

export function clearMailWakeTimerHandle(timer: ReturnType<typeof setTimeout> | undefined): undefined {
  if (timer) clearTimeout(timer);
  return undefined;
}

function inspectFleet(input: string): FleetRef | undefined {
  const root = resolve(input);
  const fleetFile = resolve(root, ".vivi", "fleet.json");
  if (!existsSync(fleetFile)) return undefined;
  const config = jsonFile(fleetFile);
  if (!config) return undefined;
  return { root, fleetId: fleetIdOf(config, root), fleetFile };
}

function sessionLabel(ctx: ExtensionContext): string {
  return `pi:${ctx.sessionManager.getSessionId()}`;
}

function entriesForSession(ctx: ExtensionContext): AttachmentEntry[] {
  const entries = ctx.sessionManager.getBranch();
  const result: AttachmentEntry[] = [];
  for (const entry of entries) {
    if (entry.type !== "custom" || entry.customType !== ATTACHMENT_ENTRY) continue;
    const data = entry.data as Partial<AttachmentEntry> | undefined;
    if (
      (data?.action === "attach" || data?.action === "detach") &&
      typeof data.root === "string" &&
      typeof data.fleetId === "string"
    ) {
      result.push(data as AttachmentEntry);
    }
  }
  return result;
}

function restoreAttachments(ctx: ExtensionContext): void {
  state.attachments.clear();
  const label = sessionLabel(ctx);
  for (const entry of entriesForSession(ctx)) {
    const fleet = inspectFleet(entry.root);
    if (!fleet || fleet.fleetId !== entry.fleetId) continue;
    if (entry.action === "detach") {
      state.attachments.delete(fleet.root);
      continue;
    }
    const baseline = jsonFile(resolve(fleet.root, ".vivi", "mind-baseline.json"));
    const owner = (baseline?.mind_session as JsonObject | undefined)?.label;
    if (owner === label) state.attachments.set(fleet.root, fleet);
  }
}

function monitorEntriesForSession(ctx: ExtensionContext): MonitorEntry[] {
  const entries = ctx.sessionManager.getBranch();
  const result: MonitorEntry[] = [];
  for (const entry of entries) {
    if (entry.type !== "custom" || entry.customType !== MONITOR_ENTRY) continue;
    const data = entry.data as Partial<MonitorEntry> | undefined;
    if (
      (data?.action === "attach" || data?.action === "detach") &&
      typeof data.root === "string" &&
      typeof data.fleetId === "string"
    ) {
      result.push(data as MonitorEntry);
    }
  }
  return result;
}

function restoreMonitors(ctx: ExtensionContext): void {
  state.monitors.clear();
  for (const entry of monitorEntriesForSession(ctx)) {
    const fleet = inspectFleet(entry.root);
    if (!fleet || fleet.fleetId !== entry.fleetId) continue;
    if (entry.action === "detach") state.monitors.delete(fleet.root);
    else state.monitors.set(fleet.root, fleet);
  }
}

function appendAttachmentEntry(pi: ExtensionAPI, fleet: FleetRef, action: "attach" | "detach"): void {
  pi.appendEntry(ATTACHMENT_ENTRY, { action, root: fleet.root, fleetId: fleet.fleetId } satisfies AttachmentEntry);
}

function appendMonitorEntry(pi: ExtensionAPI, fleet: FleetRef, action: "attach" | "detach"): void {
  pi.appendEntry(MONITOR_ENTRY, { action, root: fleet.root, fleetId: fleet.fleetId } satisfies MonitorEntry);
}

function restoreView(ctx: ExtensionContext): void {
  state.viewMode = "expanded";
  state.focusedFleetId = undefined;
  for (const entry of ctx.sessionManager.getBranch()) {
    if (entry.type !== "custom" || entry.customType !== VIEW_ENTRY) continue;
    const data = entry.data as Partial<ViewEntry> | undefined;
    if (data?.mode !== "compact" && data?.mode !== "expanded" && data?.mode !== "focus") continue;
    state.viewMode = data.mode;
    state.focusedFleetId = data.mode === "focus" && typeof data.fleetId === "string" ? data.fleetId : undefined;
  }
}

function setView(pi: ExtensionAPI, mode: FleetViewMode, fleetId?: string): void {
  state.viewMode = mode;
  state.focusedFleetId = mode === "focus" ? fleetId : undefined;
  pi.appendEntry(VIEW_ENTRY, { mode, fleetId: state.focusedFleetId } satisfies ViewEntry);
  renderWidget(state.ctx);
}

function restoreLoopIntent(ctx: ExtensionContext): LoopEntry | undefined {
  let intent: LoopEntry | undefined;
  for (const entry of ctx.sessionManager.getBranch()) {
    if (entry.type !== "custom" || entry.customType !== LOOP_ENTRY) continue;
    const data = entry.data as Partial<LoopEntry> | undefined;
    if (typeof data?.running !== "boolean") continue;
    const intervalSec = numeric(data.intervalSec);
    if (intervalSec < MIN_INTERVAL_SEC) continue;
    intent = { running: data.running, intervalSec };
  }
  return intent;
}

function saveLoopIntent(pi: ExtensionAPI, running: boolean): void {
  pi.appendEntry(LOOP_ENTRY, { running, intervalSec: state.scheduler.getIntervalSec() } satisfies LoopEntry);
}

function parseDuration(value: string | undefined): number {
  if (!value?.trim()) return DEFAULT_INTERVAL_SEC;
  const match = value.trim().toLowerCase().match(/^(\d+(?:\.\d+)?)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours)?$/);
  if (!match) throw new Error(`invalid duration: ${value}`);
  const amount = Number(match[1]);
  const unit = match[2] ?? "s";
  const multiplier = unit.startsWith("h") ? 3600 : unit.startsWith("m") ? 60 : 1;
  const seconds = Math.round(amount * multiplier);
  if (!Number.isFinite(seconds) || seconds < MIN_INTERVAL_SEC) {
    throw new Error(`interval must be at least ${MIN_INTERVAL_SEC} seconds`);
  }
  return seconds;
}

function shellSafePath(path: string): string {
  return path.replace(/[\r\n]/g, " ");
}

function compactState(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "unknown";
}

function observedRuntimeState(runtime: JsonObject | undefined): string {
  const declared = compactState(runtime?.state ?? "unknown");
  if (declared !== "unknown") return declared;
  const process = compactState(runtime?.process_state ?? "unknown");
  return process;
}

function roleState(role: JsonObject): string {
  const runtime = role.runtime as JsonObject | undefined;
  return observedRuntimeState(runtime) !== "unknown"
    ? observedRuntimeState(runtime)
    : compactState(role.state ?? "unknown");
}

function roleCount(group: Record<string, JsonObject> | undefined): string {
  if (!group) return "0";
  return Object.values(group).filter((row) => roleState(row) !== "unknown").length.toString();
}

function signalCount(snapshot: Snapshot | undefined): number {
  return Array.isArray(snapshot?.signals) ? snapshot.signals.length : 0;
}

function snapshotSummary(fleet: FleetRef, snapshot: Snapshot): string {
  const posture = compactState((snapshot.fleet_posture as JsonObject | undefined)?.mode ?? "unknown");
  const hands = snapshot.hands as Record<string, JsonObject> | undefined;
  const heads = snapshot.heads as Record<string, JsonObject> | undefined;
  const operator = snapshot.operator as JsonObject | undefined;
  const integration = snapshot.integration as JsonObject | undefined;
  const openOperator = compactState(operator?.open_count ?? 0);
  const pendingRtm = compactState(integration?.pending_rtm_count ?? 0);
  return `${fleet.fleetId} posture=${posture} signals=${signalCount(snapshot)} hands=${roleCount(hands)} heads=${roleCount(heads)} operator=${openOperator} rtm=${pendingRtm}`;
}

function safeRuntime(value: unknown): JsonObject | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const runtime = value as JsonObject;
  return {
    kind: runtime.kind,
    target: runtime.target,
    state: runtime.state,
    process_state: runtime.process_state,
    confidence: runtime.confidence,
    model: runtime.model,
  };
}

function safeSnapshot(snapshot: Snapshot): JsonObject {
  const roles = (group: Record<string, JsonObject> | undefined) =>
    Object.fromEntries(
      Object.entries(group ?? {}).map(([name, row]) => [name, {
        actionable: row.actionable,
        tasks_open: row.tasks_open,
        needs_open: row.needs_open,
        runtime: safeRuntime(row.runtime),
        model_provenance: row.model_provenance,
      }]),
    );
  return {
    fleet_id: snapshot.fleet_id,
    fleet_posture: snapshot.fleet_posture,
    signals: snapshot.signals ?? [],
    fingerprint: snapshot.fingerprint ?? {},
    hands: roles(snapshot.hands),
    heads: roles(snapshot.heads),
    operator: snapshot.operator,
    mind: snapshot.mind,
    integration: snapshot.integration,
    steward: snapshot.steward ? {
      enabled: snapshot.steward.enabled,
      armed: snapshot.steward.armed,
      tripped: snapshot.steward.tripped,
      runtime: safeRuntime(snapshot.steward.runtime),
    } : undefined,
    partial: snapshot.partial,
  };
}

function preflightCounts(snapshot: Snapshot): { actionable: number; mail: number; needs: number; rtm: number } {
  let actionable = 0;
  let mail = numeric((snapshot.mind as JsonObject | undefined)?.inbox_unread);
  let needs = numeric((snapshot.operator as JsonObject | undefined)?.open_count);
  for (const group of [snapshot.hands, snapshot.heads]) {
    for (const row of Object.values(group ?? {})) {
      actionable += numeric(row.actionable);
      mail += numeric(row.inbox_unread);
      needs += numeric(row.needs_open);
    }
  }
  return {
    actionable,
    mail,
    needs,
    rtm: numeric((snapshot.integration as JsonObject | undefined)?.pending_rtm_count),
  };
}

function preflightRoleLine(group: Record<string, JsonObject> | undefined, head: boolean): string {
  return Object.entries(group ?? {}).map(([name, row]) => {
    const stateName = roleGlyph(row).state;
    const shortName = head ? name.replace(/^head-/, "") : name.replace(/^hand-/, "h");
    const metric = head
      ? row.sweep_due === true ? "due" : row.sweep_enabled === true ? "on" : "—"
      : String(numeric(row.actionable));
    return `${shortName}=${stateName}/${metric}`;
  }).join(" ");
}

function preflightLine(fleet: FleetRef, snapshot: Snapshot | undefined): string[] {
  if (!snapshot) return [`  ${fleet.fleetId}: sensors=pending`];
  const counts = preflightCounts(snapshot);
  const signals = (snapshot.signals ?? []).slice(0, 12).map((signal) => signal.slice(0, 100));
  const captured = typeof snapshot.at === "string" ? snapshot.at : "unknown";
  const lines = [
    `  ${fleet.fleetId}: captured=${captured}${snapshot.partial ? " partial" : ""}`,
    `    work=${counts.actionable} mail=${counts.mail} operator-needs=${counts.needs} pending-rtm=${counts.rtm}`,
    `    Hands: ${preflightRoleLine(snapshot.hands, false) || "none"}`,
    `    Heads: ${preflightRoleLine(snapshot.heads, true) || "none"}`,
    `    signals: ${signals.length > 0 ? signals.join(", ") : "none"}`,
  ];
  if ((snapshot.signals?.length ?? 0) > signals.length) {
    lines[lines.length - 1] += ` +${(snapshot.signals?.length ?? 0) - signals.length} more`;
  }
  return lines;
}

function cyclePayload(): string {
  const fleets = [...state.attachments.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId));
  const slugs = fleets.map((fleet) => fleet.fleetId).join(",");
  const roots = fleets.map((fleet) => `  ${fleet.fleetId}: ${fleet.root}`).join("\n");
  const preflight = fleets.flatMap((fleet) => preflightLine(fleet, state.snapshots.get(fleet.root))).join("\n");
  return `FLEET_CYCLE fleets=${slugs}\nRoots:\n${roots}\n\nSensor preflight (observation only; Mind owns disposition):\n${preflight}`;
}

const ACTIVE_RUNTIME_STATES = new Set(["starting", "submitting", "running"]);

function numeric(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function roleGlyph(row: JsonObject | undefined): { glyph: string; color: string; state: string } {
  const runtime = row?.runtime as JsonObject | undefined;
  const stateName = observedRuntimeState(runtime) !== "unknown"
    ? observedRuntimeState(runtime)
    : compactState(row?.state ?? "unknown");
  const lowConfidence = runtime?.confidence === "low";
  if (ACTIVE_RUNTIME_STATES.has(stateName)) return { glyph: "●", color: lowConfidence ? "warning" : "success", state: stateName };
  if (stateName === "approval_required") return { glyph: "!", color: "warning", state: stateName };
  if (stateName === "failed" || stateName === "stopped") return { glyph: "×", color: "error", state: stateName };
  if (stateName === "unknown") return { glyph: "?", color: "dim", state: stateName };
  return { glyph: "○", color: "dim", state: stateName };
}

type RoleClass = "mind" | "hand" | "head";

type ClassifiedRoles = {
  minds: Array<[string, JsonObject]>;
  hands: Array<[string, JsonObject]>;
  heads: Array<[string, JsonObject]>;
};

function roleClass(fleet: FleetRef, name: string, sensorClass: "hand" | "head"): RoleClass {
  if (sensorClass === "head") return "head";
  const config = jsonFile(fleet.fleetFile);
  const hands = config?.hands as Record<string, JsonObject> | undefined;
  const hunters = config?.hunters as Record<string, JsonObject> | undefined;
  const role = compactState(hands?.[name]?.role ?? hunters?.[name]?.role ?? "hand");
  return role === "managed-mind" || role === "mind" ? "mind" : "hand";
}

function classifiedRoles(fleet: FleetRef, snapshot: Snapshot | undefined): ClassifiedRoles {
  const roles: ClassifiedRoles = { minds: [], hands: [], heads: [] };
  for (const [name, row] of Object.entries(snapshot?.hands ?? {})) {
    roles[roleClass(fleet, name, "hand") === "mind" ? "minds" : "hands"].push([name, row]);
  }
  roles.heads.push(...Object.entries(snapshot?.heads ?? {}));
  return roles;
}

function roleToken(name: string, row: JsonObject, roleClass: RoleClass, theme: any): string {
  const status = roleGlyph(row);
  const shortName = roleClass === "head"
    ? name.replace(/^head-/, "")
    : roleClass === "mind"
      ? name.replace(/^mind-/, "")
      : name.replace(/^hand-/, "h");
  const metric = roleClass === "head"
    ? row.sweep_due === true ? "due" : row.sweep_enabled === true ? "on" : "—"
    : String(numeric(row.actionable ?? row.tasks_open));
  const labelColor = status.state === "unknown" ? "dim" : "muted";
  return `${theme.fg(status.color, status.glyph)} ${theme.fg(labelColor, shortName)}${theme.fg("dim", `:${metric}`)}`;
}

function roleGroups(): ClassifiedRoles {
  const roles: ClassifiedRoles = { minds: [], hands: [], heads: [] };
  for (const fleet of state.attachments.values()) {
    const classified = classifiedRoles(fleet, state.snapshots.get(fleet.root));
    roles.minds.push(...classified.minds);
    roles.hands.push(...classified.hands);
    roles.heads.push(...classified.heads);
  }
  return roles;
}

function panelMetrics(): { activeMinds: number; totalMinds: number; activeHands: number; totalHands: number; activeHeads: number; totalHeads: number; mail: number; needs: number; rtm: number; signals: number; actionable: number } {
  let mail = 0;
  let needs = 0;
  let rtm = 0;
  let signals = 0;
  let actionable = 0;
  for (const snapshot of state.snapshots.values()) {
    signals += signalCount(snapshot);
    mail += numeric((snapshot.mind as JsonObject | undefined)?.inbox_unread);
    needs += numeric((snapshot.operator as JsonObject | undefined)?.open_count);
    rtm += numeric((snapshot.integration as JsonObject | undefined)?.pending_rtm_count);
    for (const group of [snapshot.hands, snapshot.heads]) {
      for (const row of Object.values(group ?? {})) {
        mail += numeric(row.inbox_unread);
        needs += numeric(row.needs_open);
        actionable += numeric(row.actionable);
      }
    }
  }
  const { minds, hands, heads } = roleGroups();
  return {
    activeMinds: minds.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length,
    totalMinds: minds.length,
    activeHands: hands.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length,
    totalHands: hands.length,
    activeHeads: heads.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length,
    totalHeads: heads.length,
    mail,
    needs,
    rtm,
    signals,
    actionable,
  };
}

function configuredCycleInterval(fleet: FleetRef): number {
  const config = jsonFile(fleet.fleetFile);
  const loop = config?.mind_loop as JsonObject | undefined;
  const raw = loop?.interval_sec ?? config?.loop_interval_sec;
  const interval = numeric(raw);
  return interval >= MIN_INTERVAL_SEC ? interval : DEFAULT_INTERVAL_SEC;
}

function formatDuration(seconds: number | undefined): string {
  if (seconds === undefined || !Number.isFinite(seconds)) return "—";
  if (seconds <= 0) return "due";
  if (seconds < 60) return `${Math.ceil(seconds)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.ceil(seconds % 60);
  if (minutes < 60) return `${minutes}m${remainder ? ` ${remainder}s` : ""}`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h${minutes % 60 ? ` ${minutes % 60}m` : ""}`;
}

function timestampSeconds(value: unknown): number | undefined {
  if (typeof value !== "string") return undefined;
  const time = Date.parse(value);
  return Number.isFinite(time) ? time / 1000 : undefined;
}

function fleetNextCycle(fleet: FleetRef, mode: "mind" | "monitor", baseline: JsonObject | undefined): string {
  const nextCycleAt = state.scheduler.getDeadlineMs();
  if (mode === "mind" && state.scheduler.isRunning() && nextCycleAt !== undefined) {
    return `next ${formatDuration(nextCycleAt / 1000 - Date.now() / 1000)}`;
  }
  const lastCycle = timestampSeconds(baseline?.last_cycle_at);
  if (lastCycle === undefined) return "next —";
  return `next est ${formatDuration(lastCycle + configuredCycleInterval(fleet) - Date.now() / 1000)}`;
}

function fleetSnapshot(fleet: FleetRef, mode: "mind" | "monitor"): Snapshot | undefined {
  return mode === "mind" ? state.snapshots.get(fleet.root) : state.monitorSnapshots.get(fleet.root);
}

function fleetBaseline(fleet: FleetRef, mode: "mind" | "monitor"): JsonObject | undefined {
  return mode === "mind" ? state.baselines.get(fleet.root) : state.monitorBaselines.get(fleet.root);
}

function fleetCompactRow(fleet: FleetRef, mode: "mind" | "monitor", theme: any): string {
  const snapshot = fleetSnapshot(fleet, mode);
  const baseline = fleetBaseline(fleet, mode);
  const posture = compactState((snapshot?.fleet_posture as JsonObject | undefined)?.mode ?? "unknown");
  const modeText = mode === "mind" ? "Mind" : "Monitor";
  const modeColor = mode === "mind" ? "accent" : "muted";
  const { minds, hands, heads } = classifiedRoles(fleet, snapshot);
  const activeMinds = minds.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length;
  const activeHands = hands.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length;
  const activeHeads = heads.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length;
  const counts = snapshot ? preflightCounts(snapshot) : { actionable: 0, mail: 0, needs: 0, rtm: 0 };
  const signals = signalCount(snapshot);
  const signalText = signals > 0 ? theme.fg("warning", `!${signals}`) : theme.fg("dim", "!0");
  const external = mode === "mind" && state.externalLoops.get(fleet.root)?.running ? theme.fg("warning", " !ext") : "";
  const roleCounts = [
    minds.length > 0 ? `M${activeMinds}/${minds.length}` : undefined,
    hands.length > 0 ? `H${activeHands}/${hands.length}` : undefined,
    heads.length > 0 ? `Hd${activeHeads}/${heads.length}` : undefined,
  ].filter(Boolean).join(" · ");
  return ` ${theme.fg("accent", "◈")} ${theme.bold(fleet.fleetId)} ${theme.fg(modeColor, modeText)} ${theme.fg(posture === "growth" ? "success" : "dim", posture)}  ${theme.fg("dim", `cycle ${baseline ? baselineCycle(baseline) : "—"}`)}${roleCounts ? ` · ${theme.fg("dim", roleCounts)}` : ""} · ${theme.fg("dim", `work ${counts.actionable}`)} · ${theme.fg("dim", `✉${counts.mail}`)} · ${theme.fg("dim", `⚑${counts.needs}`)} · ${theme.fg("dim", `↻${counts.rtm}`)} · ${signalText} · ${theme.fg("dim", fleetNextCycle(fleet, mode, baseline))}${external}`;
}

function fleetDetailRows(fleet: FleetRef, mode: "mind" | "monitor", theme: any): string[] {
  const snapshot = fleetSnapshot(fleet, mode);
  const baseline = fleetBaseline(fleet, mode);
  const event = mode === "monitor" ? state.monitorEvents.get(fleet.root) : undefined;
  const posture = compactState((snapshot?.fleet_posture as JsonObject | undefined)?.mode ?? "unknown");
  const cycle = baseline ? `cycle ${baselineCycle(baseline)}` : "cycle —";
  const cyclePeriod = `${configuredCycleInterval(fleet)}s`;
  const timing = fleetNextCycle(fleet, mode, baseline);
  const modeText = mode === "mind" ? "Mind" : "Monitor";
  const modeColor = mode === "mind" ? "accent" : "muted";
  const external = mode === "mind" && state.externalLoops.get(fleet.root)?.running ? theme.fg("warning", " !ext") : "";
  const lines = [
    ` ${theme.fg("accent", "◈")} ${theme.bold(fleet.fleetId)} ${theme.fg(modeColor, modeText)} ${theme.fg(posture === "growth" ? "success" : "dim", posture)}  ${theme.fg("dim", `${cycle} · period ${cyclePeriod} · ${timing}`)}${external}`,
  ];
  if (!snapshot) {
    lines.push(`   ${theme.fg("dim", "sensors=pending")}`);
    return lines;
  }
  const { minds, hands, heads } = classifiedRoles(fleet, snapshot);
  const counts = preflightCounts(snapshot);
  const signalText = signalCount(snapshot) > 0 ? theme.fg("warning", `!${signalCount(snapshot)}`) : theme.fg("dim", "!0");
  const addRoleRow = (label: string, roles: Array<[string, JsonObject]>, roleClass: RoleClass) => {
    if (roles.length === 0) return;
    const active = roles.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length;
    const tokens = roles.map(([name, row]) => roleToken(name, row, roleClass, theme)).join("  ");
    lines.push(`   ${theme.fg("muted", label)} ${theme.fg("dim", `${active}/${roles.length}`)}  ${tokens}`);
  };
  addRoleRow("Mind", minds, "mind");
  addRoleRow("Hand", hands, "hand");
  addRoleRow("Head", heads, "head");
  lines.push(`   ${theme.fg("muted", "Vivi")} ${theme.fg("success", "●")} ${theme.fg("dim", `work ${counts.actionable}`)}  ${theme.fg("dim", `✉${counts.mail}`)}  ${theme.fg("dim", `⚑${counts.needs}`)}  ${theme.fg("dim", `↻${counts.rtm}`)}  ${signalText}`);
  const summary = event
    ? `${event.acted ? "acted" : "quiet"} · ${event.summary}`
    : baselineSummary(baseline ?? {});
  lines.push(`   ${theme.fg("dim", `last: ${summary}`)}`);
  return lines;
}

class FleetPanel {
  constructor(private readonly theme: any) {}

  render(width: number): string[] {
    const fleets = [...state.attachments.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId));
    const monitors = [...state.monitors.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId));
    const candidate = state.candidate && !state.attachments.has(state.candidate.root) && !state.monitors.has(state.candidate.root) ? state.candidate : undefined;
    if (fleets.length === 0 && monitors.length === 0) {
      if (!candidate) return [];
      return [truncateToWidth(
        `${this.theme.fg("dim", "◇")} ${this.theme.fg("muted", "candidate")} ${this.theme.fg("accent", candidate.fleetId)} ${this.theme.fg("dim", shellSafePath(candidate.root))} ${this.theme.fg("accent", "→ /fleet attach .")}`,
        width,
        "…",
      )];
    }

    const lines: string[] = [];
    const renderFleet = (fleet: FleetRef, mode: "mind" | "monitor") => {
      const expanded = state.viewMode === "expanded" ||
        (state.viewMode === "focus" && state.focusedFleetId === fleet.fleetId);
      const rows = expanded
        ? fleetDetailRows(fleet, mode, this.theme)
        : [fleetCompactRow(fleet, mode, this.theme)];
      for (const line of rows) lines.push(truncateToWidth(line, width, "…"));
      if (expanded) lines.push("");
    };
    for (const fleet of fleets) renderFleet(fleet, "mind");
    for (const fleet of monitors) renderFleet(fleet, "monitor");
    if (state.lastError) {
      lines.push(truncateToWidth(`${this.theme.fg("error", "×")} ${this.theme.fg("error", state.lastError)}`, width, "…"));
    }
    return lines;
  }

  invalidate(): void {}
}

function renderWidget(ctx?: ExtensionContext): void {
  if (!ctx) return;
  const fleets = [...state.attachments.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId));
  const monitors = [...state.monitors.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId));
  const candidate = state.candidate && !state.attachments.has(state.candidate.root) && !state.monitors.has(state.candidate.root) ? state.candidate : undefined;
  if (fleets.length === 0 && monitors.length === 0 && !candidate) {
    ctx.ui.setWidget(WIDGET_KEY, undefined);
    ctx.ui.setStatus(STATUS_KEY, undefined);
    return;
  }
  ctx.ui.setWidget(WIDGET_KEY, (_tui, theme) => new FleetPanel(theme));
  const metrics = panelMetrics();
  ctx.ui.setStatus(
    STATUS_KEY,
    fleets.length > 0
      ? `◈ ${fleets.map((fleet) => fleet.fleetId).join(",")}${metrics.totalMinds > 0 ? ` · M${metrics.activeMinds}/${metrics.totalMinds}` : ""}${metrics.totalHands > 0 ? ` · H${metrics.activeHands}/${metrics.totalHands}` : ""}${metrics.totalHeads > 0 ? ` · Hd${metrics.activeHeads}/${metrics.totalHeads}` : ""} · ✉${metrics.mail} · !${metrics.signals}${monitors.length > 0 ? ` · Mon${monitors.length}` : ""}`
      : monitors.length > 0
        ? `◌ monitor:${monitors.map((fleet) => fleet.fleetId).join(",")} · M${monitors.length}`
        : `◇ candidate ${candidate?.fleetId}`,
  );
}

async function execJson(
  pi: ExtensionAPI,
  command: string,
  args: string[],
  cwd?: string,
  timeout = 30_000,
  acceptedCodes: number[] = [0],
): Promise<JsonObject> {
  const result = await pi.exec(command, args, { cwd, timeout });
  if (!acceptedCodes.includes(result.code)) {
    const detail = (result.stderr || result.stdout || `${command} exited ${result.code}`).trim().replace(/\s+/g, " ");
    throw new Error(detail.slice(0, 400));
  }
  try {
    const value = JSON.parse(result.stdout);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("JSON result is not an object");
    return value as JsonObject;
  } catch (error) {
    throw new Error(`${command} returned invalid JSON: ${error instanceof Error ? error.message : String(error)}`);
  }
}

async function validateFleet(pi: ExtensionAPI, fleet: FleetRef): Promise<void> {
  await execJson(pi, "python3", [VERIFY_SCRIPT, "--project", fleet.root, "--fleet", fleet.fleetId, "--json"], undefined, 30_000);
}

async function readBaseline(pi: ExtensionAPI, fleet: FleetRef): Promise<JsonObject> {
  return execJson(pi, "python3", [BASELINE_SCRIPT, "get", "--project", fleet.root, "--fleet", fleet.fleetId], undefined, 15_000);
}

async function readExternalLoop(pi: ExtensionAPI, fleet: FleetRef): Promise<ExternalLoop> {
  try {
    return await execJson(pi, "python3", [LOOP_SCRIPT, "--project", fleet.root, "--fleet", fleet.fleetId, "status"], undefined, 15_000) as ExternalLoop;
  } catch (error) {
    return { state: { error: error instanceof Error ? error.message : String(error) } };
  }
}

async function readSnapshot(pi: ExtensionAPI, fleet: FleetRef, readOnly = false): Promise<Snapshot> {
  // fleet-sensors.py uses exit code 2 for a partial-but-usable snapshot.
  const args = [SENSOR_SCRIPT, "--project", fleet.root, "--fleet", fleet.fleetId, "--json"];
  if (readOnly) args.push("--no-watch");
  return await execJson(
    pi,
    "python3",
    args,
    undefined,
    45_000,
    [0, 2],
  ) as Snapshot;
}

async function refreshFleet(pi: ExtensionAPI, fleet: FleetRef, wakeOnChange: boolean, readOnly = false): Promise<Snapshot> {
  const [snapshot, external, baseline] = await Promise.all([
    readSnapshot(pi, fleet, readOnly),
    readExternalLoop(pi, fleet),
    readBaseline(pi, fleet),
  ]);
  const previous = state.snapshots.get(fleet.root);
  state.snapshots.set(fleet.root, snapshot);
  state.baselines.set(fleet.root, baseline);
  state.externalLoops.set(fleet.root, external);
  if (state.scheduler.isRunning() && external.running !== false) {
    stopTimers();
    state.lastError = external.running
      ? `external fleet-loop.py detected for ${fleet.fleetId}; internal loop stopped`
      : `cannot verify external fleet-loop.py state for ${fleet.fleetId}; internal loop stopped`;
  }
  if (wakeOnChange && snapshotHasActionableChange(previous, snapshot)) queueCycle(pi, `sensor change: ${fleet.fleetId}`);
  return snapshot;
}

async function refreshAll(pi: ExtensionAPI, wakeOnChange = false): Promise<void> {
  if (state.pollInFlight) return;
  state.pollInFlight = true;
  state.lastPollAt = new Date().toISOString();
  try {
    const fleets = [...state.attachments.values()];
    await Promise.all(fleets.map(async (fleet) => {
      try {
        await refreshFleet(pi, fleet, wakeOnChange);
      } catch (error) {
        state.lastError = `${fleet.fleetId}: ${error instanceof Error ? error.message : String(error)}`;
      }
    }));
  } finally {
    state.pollInFlight = false;
    renderWidget(state.ctx!);
  }
}

function baselineCycle(baseline: JsonObject): number {
  return numeric(baseline.last_cycle);
}

function baselineSummary(baseline: JsonObject): string {
  const raw = typeof baseline.last_cycle_summary === "string" ? baseline.last_cycle_summary : "cycle observed";
  const compact = raw.replace(/[\r\n\t]+/g, " ").replace(/\s+/g, " ").trim();
  if (/pi fleet takeover/i.test(compact)) return "Mind takeover";
  if (/pi fleet attach/i.test(compact)) return "Mind attached";
  if (/operator.*detach|detach.*operator/i.test(compact)) return "Operator detached";
  if (/pi fleet detach/i.test(compact)) return "Mind detached";
  if (/^(sleep|quiet|sensor-gated quiet)/i.test(compact)) return "quiet";
  return compact.slice(0, 100) || "cycle observed";
}

async function refreshMonitor(pi: ExtensionAPI, fleet: FleetRef, detectCycle: boolean): Promise<void> {
  const [baseline, snapshot] = await Promise.all([readBaseline(pi, fleet), readSnapshot(pi, fleet, true)]);
  const previous = state.monitorBaselines.get(fleet.root);
  const cycle = baselineCycle(baseline);
  state.monitorBaselines.set(fleet.root, baseline);
  state.monitorSnapshots.set(fleet.root, snapshot);
  if (detectCycle && previous && cycle !== baselineCycle(previous)) {
    state.monitorEvents.set(fleet.root, {
      cycle,
      at: typeof baseline.last_cycle_at === "string" ? baseline.last_cycle_at : undefined,
      acted: baseline.last_cycle_acted === true,
      summary: baselineSummary(baseline),
      signalCount: signalCount(snapshot),
    });
  }
}

async function refreshMonitors(pi: ExtensionAPI, detectCycle = true): Promise<void> {
  const fleets = [...state.monitors.values()];
  await Promise.all(fleets.map(async (fleet) => {
    try {
      await refreshMonitor(pi, fleet, detectCycle);
    } catch (error) {
      state.lastError = `monitor ${fleet.fleetId}: ${error instanceof Error ? error.message : String(error)}`;
    }
  }));
  renderWidget(state.ctx);
}

function stopMonitorTimer(): void {
  if (state.monitorTimer) clearInterval(state.monitorTimer);
  state.monitorTimer = undefined;
}

function startMonitorTimer(pi: ExtensionAPI): void {
  stopMonitorTimer();
  state.monitorTimer = setInterval(() => {
    void refreshMonitors(pi, true);
  }, state.monitorIntervalSec * 1000);
}

function startUiTimer(): void {
  if (state.uiTimer) clearInterval(state.uiTimer);
  state.uiTimer = setInterval(() => {
    if (state.ctx && (state.scheduler.isRunning() || state.monitors.size > 0)) renderWidget(state.ctx);
  }, 1000);
}

function stopUiTimer(): void {
  if (state.uiTimer) clearInterval(state.uiTimer);
  state.uiTimer = undefined;
}

function clearScheduledTimer(): void {
  if (state.loopTimer) clearTimeout(state.loopTimer);
  state.loopTimer = undefined;
}

function clearTimerHandles(): void {
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = undefined;
  clearScheduledTimer();
  stopMailWakeSockets();
  state.mailWakeTimer = clearMailWakeTimerHandle(state.mailWakeTimer);
  state.cycleQueued = false;
}

function stopTimers(): void {
  clearTimerHandles();
  state.scheduler.stop();
}

// Reconcile the single real scheduled one-shot with the policy deadline. The
// scheduled cycle is a generation-safe one-shot, not a repeating interval: any
// accepted cycle invalidates the pending callback (see queueCycle), and
// agent_settled arms the next deadline at completion+interval (see
// onAgentSettled). The independent poll timer never touches this.
function syncScheduledTimer(pi: ExtensionAPI): void {
  clearScheduledTimer();
  const deadline = state.scheduler.getDeadlineMs();
  if (deadline === undefined || !state.scheduler.isRunning()) return;
  const generation = state.scheduler.getGeneration();
  const delay = Math.max(0, deadline - Date.now());
  state.loopTimer = setTimeout(() => onScheduledFire(pi, generation), delay);
}

function onScheduledFire(pi: ExtensionAPI, generation: number): void {
  if (!loopGenerationIsCurrent(state.scheduler.isRunning(), state.scheduler.getGeneration(), generation)) return;
  // Refresh immediately before scheduled delivery so the preflight is not
  // merely the last 60-second poll snapshot.
  const deliver = state.scheduler.fire();
  syncScheduledTimer(pi);
  if (!deliver) return;
  void refreshAll(pi, false).then(() => {
    if (!loopGenerationIsCurrent(state.scheduler.isRunning(), state.scheduler.getGeneration(), generation)) return;
    queueCycle(pi, "scheduled cycle");
    renderWidget(state.ctx);
  });
}

function startTimers(pi: ExtensionAPI, intervalSec: number = state.scheduler.getIntervalSec()): void {
  clearTimerHandles();
  state.scheduler.start(Date.now(), intervalSec);
  state.startedAt ??= new Date().toISOString();
  state.pollTimer = setInterval(() => {
    void refreshAll(pi, true);
  }, POLL_INTERVAL_MS);
  syncScheduledTimer(pi);
  startConfiguredMailWakeSocket(pi);
  const now = Date.now();
  const dueCycle = mailWakeDueOnLoopStart(state.scheduler.isRunning(), state.mailWakeDebouncer, now);
  if (dueCycle) {
    applyMailWakeDispatchResults(state.mailWakeDebouncer, [dueCycle], (cycle) => dispatchMailWakeCycle(pi, cycle), now);
  }
  saveMailWakeState(pi);
  scheduleMailWakeTimer(pi);
  renderWidget(state.ctx!);
}

// Cadence change while running: replace the pending scheduled deadline with
// now+interval and re-arm the one-shot. Running and in-flight state are
// preserved (an in-flight cycle is not forgotten across an update). The
// independent poll timer is left running.
function updateTimers(pi: ExtensionAPI, intervalSec: number): void {
  state.scheduler.update(Date.now(), intervalSec);
  syncScheduledTimer(pi);
  renderWidget(state.ctx!);
}

function queueCycle(pi: ExtensionAPI, reason: string, allowBusyFollowUp = false): boolean {
  if (!state.scheduler.isRunning() || state.attachments.size === 0 || state.cycleQueued || (state.scheduler.isInFlight() && !allowBusyFollowUp)) return false;
  const ctx = state.ctx;
  if (!ctx) return false;
  state.cycleQueued = true;
  try {
    const payload = `${cyclePayload()}\n\nReason: ${reason}`;
    const delivery = ctx.isIdle() ? undefined : "followUp";
    pi.sendUserMessage(payload, delivery ? { deliverAs: delivery } : undefined);
    state.lastCycleAt = new Date().toISOString();
    state.scheduler.accept(Date.now());
    syncScheduledTimer(pi);
    return true;
  } catch (error) {
    state.lastError = error instanceof Error ? error.message : String(error);
    return false;
  } finally {
    state.cycleQueued = false;
  }
}

function mailWakeReason(cycle: MailWakeCycle): string {
  return `trusted mail ${cycle.trigger}: count=${cycle.count} message_ids=${cycle.messageIds.join(",")}`;
}

function saveMailWakeState(pi: ExtensionAPI): void {
  pi.appendEntry(MAIL_WAKE_ENTRY, mailWakeEntryFromSnapshot(state.mailWakeDebouncer.snapshot()));
}

function dispatchMailWakeCycle(pi: ExtensionAPI, cycle: MailWakeCycle): boolean {
  const sent = queueCycle(pi, mailWakeReason(cycle), true);
  if (!sent) state.lastError = "trusted mail wake queued for retry; active Fleet cycle was unavailable";
  renderWidget(state.ctx);
  return sent;
}

function scheduleMailWakeTimer(pi: ExtensionAPI): void {
  state.mailWakeTimer = clearMailWakeTimerHandle(state.mailWakeTimer);
  const deadline = state.mailWakeDebouncer.nextDeadlineMs();
  if (deadline === undefined) return;
  const delay = Math.max(0, deadline - Date.now());
  state.mailWakeTimer = setTimeout(() => {
    const now = Date.now();
    const cycle = state.mailWakeDebouncer.due(now);
    if (cycle) {
      applyMailWakeDispatchResults(state.mailWakeDebouncer, [cycle], (dueCycle) => dispatchMailWakeCycle(pi, dueCycle), now);
    }
    saveMailWakeState(pi);
    scheduleMailWakeTimer(pi);
  }, delay);
}

function restoreMailWakeState(ctx: ExtensionContext): void {
  let snapshot: MailWakeSnapshot | undefined;
  for (const entry of ctx.sessionManager.getBranch()) {
    if (entry.type !== "custom" || entry.customType !== MAIL_WAKE_ENTRY) continue;
    snapshot = mailWakeSnapshotFromEntry(entry.data as Partial<MailWakeStateEntry> | undefined) ?? snapshot;
  }
  state.mailWakeDebouncer = new MailWakeDebouncer(MAIL_WAKE_QUIET_MS, snapshot);
}

function acceptMailWakeEvent(pi: ExtensionAPI, payload: unknown): JsonObject {
  const event = parseTrustedMailWakePayload(payload);
  const now = Date.now();
  const cycles = state.mailWakeDebouncer.ingest(event, now);
  const result = applyMailWakeDispatchResults(state.mailWakeDebouncer, cycles, (cycle) => dispatchMailWakeCycle(pi, cycle), now);
  saveMailWakeState(pi);
  scheduleMailWakeTimer(pi);
  return { ...result, message_count: event.messageIds.length };
}

function wakeSocketPath(fleet: FleetRef): string {
  return resolve(fleet.root, ".vivi", MAIL_WAKE_SOCKET);
}

function stopMailWakeSocket(fleet: FleetRef): void {
  const server = state.mailWakeSockets.get(fleet.root);
  state.mailWakeSockets.delete(fleet.root);
  if (server) server.close();
  const path = wakeSocketPath(fleet);
  try {
    if (existsSync(path) && statSync(path).isSocket()) unlinkSync(path);
  } catch {
    // Best-effort cleanup only; stale sockets are handled on next start.
  }
}

function stopMailWakeSockets(): void {
  for (const fleet of state.attachments.values()) stopMailWakeSocket(fleet);
}

function startConfiguredMailWakeSocket(pi: ExtensionAPI): void {
  stopMailWakeSockets();
  const selection = mailWakeEndpointPlan(
    state.scheduler.isRunning(),
    [...state.attachments.values()],
    (fleet) => jsonFile(fleet.fleetFile),
  );
  if (selection.error) {
    state.lastError = selection.error;
    renderWidget(state.ctx);
    return;
  }
  if (selection.fleet) startMailWakeSocket(pi, selection.fleet);
}

function handleMailWakeSocket(pi: ExtensionAPI, socket: Socket): void {
  let buffer = "";
  socket.setEncoding("utf8");
  socket.on("data", (chunk: string) => {
    buffer += chunk;
    if (buffer.length > MAIL_WAKE_MAX_LINE) {
      socket.end(JSON.stringify({ ok: false, error: "mail wake event too large" }) + "\n");
      return;
    }
    const index = buffer.indexOf("\n");
    if (index < 0) return;
    const line = buffer.slice(0, index);
    try {
      const result = acceptMailWakeEvent(pi, JSON.parse(line));
      socket.end(JSON.stringify(result) + "\n");
    } catch (error) {
      socket.end(JSON.stringify({
        ok: false,
        accepted: false,
        retryable: error instanceof MailWakeCapacityError ? error.retryable : undefined,
        error: error instanceof Error ? error.message : String(error),
      }) + "\n");
    }
  });
}

function startMailWakeSocket(pi: ExtensionAPI, fleet: FleetRef): void {
  if (state.mailWakeSockets.has(fleet.root)) return;
  const path = wakeSocketPath(fleet);
  try {
    if (existsSync(path)) {
      const existing = statSync(path);
      if (existing.isSocket()) unlinkSync(path);
      else throw new Error(`mail wake endpoint exists and is not a socket: ${path}`);
    }
    const server = createServer((socket) => handleMailWakeSocket(pi, socket));
    server.on("error", (error) => {
      state.lastError = `mail wake socket ${fleet.fleetId}: ${error instanceof Error ? error.message : String(error)}`;
      renderWidget(state.ctx);
    });
    server.listen(path, () => {
      chmodSync(path, 0o600);
    });
    state.mailWakeSockets.set(fleet.root, server);
  } catch (error) {
    state.lastError = `mail wake socket ${fleet.fleetId}: ${error instanceof Error ? error.message : String(error)}`;
  }
}

function onAgentSettled(pi: ExtensionAPI): void {
  state.cycleQueued = false;
  // Only a completed Fleet cycle rebases the scheduled deadline; a non-Fleet
  // agent turn is not a cycle completion and must not move the deadline.
  if (state.scheduler.isInFlight()) {
    state.scheduler.settle(Date.now());
    syncScheduledTimer(pi);
  }
}

async function attach(pi: ExtensionAPI, ctx: ExtensionContext, input: string, takeover = false): Promise<void> {
  const rootInput = input.trim() || ctx.cwd;
  const fleet = inspectFleet(rootInput === "." ? ctx.cwd : rootInput);
  if (!fleet) throw new Error(`no valid .vivi/fleet.json at ${shellSafePath(rootInput)}`);
  await validateFleet(pi, fleet);
  const baseline = await readBaseline(pi, fleet);
  const owner = (baseline.mind_session as JsonObject | undefined)?.label;
  const label = sessionLabel(ctx);
  if (owner && owner !== label) {
    if (!takeover) throw new Error(`${fleet.fleetId} is attached to another Mind session (${owner}); retry with --takeover after confirming it is dead or yielded`);
    const confirmed = await ctx.ui.confirm(
      "Take over Fleet Mind?",
      `${fleet.fleetId} is attached to ${owner}. Confirm that Mind is dead or has yielded; this overwrites the advisory lock.`,
    );
    if (!confirmed) throw new Error("takeover cancelled");
  }
  if (!owner || takeover) {
    await execJson(pi, "python3", [
      BASELINE_SCRIPT, "bump", "--project", fleet.root, "--fleet", fleet.fleetId,
      "--summary", `${takeover ? "pi fleet takeover" : "pi fleet attach"}: ${label}`,
      "--acted", "--mind-session", label, "--mind-host", hostname(),
      "--recap", `${takeover ? "Took over" : "Attached"} Mind session ${label}`,
    ], undefined, 20_000);
  }
  state.attachments.set(fleet.root, fleet);
  state.candidate = undefined;
  state.lastError = undefined;
  appendAttachmentEntry(pi, fleet, "attach");
  if (state.scheduler.isRunning()) startConfiguredMailWakeSocket(pi);
  await refreshFleet(pi, fleet, false);
  renderWidget(ctx);
  ctx.ui.notify(`Attached ${fleet.fleetId}`, "info");
}

async function monitorAttach(pi: ExtensionAPI, ctx: ExtensionContext, input: string): Promise<void> {
  const rootInput = input.trim() || ctx.cwd;
  const fleet = inspectFleet(rootInput === "." ? ctx.cwd : rootInput);
  if (!fleet) throw new Error(`no valid .vivi/fleet.json at ${shellSafePath(rootInput)}`);
  await validateFleet(pi, fleet);
  state.monitors.set(fleet.root, fleet);
  state.lastError = undefined;
  appendMonitorEntry(pi, fleet, "attach");
  await refreshMonitor(pi, fleet, false);
  startMonitorTimer(pi);
  renderWidget(ctx);
  ctx.ui.notify(`Monitoring ${fleet.fleetId} (read-only)`, "info");
}

async function monitorDetach(pi: ExtensionAPI, ctx: ExtensionContext, input: string): Promise<void> {
  const token = input.trim();
  const fleet = [...state.monitors.values()].find((item) => item.root === resolve(token) || item.fleetId === token) ??
    (token === "." || token === "" ? state.monitors.get(resolve(ctx.cwd)) : undefined);
  if (!fleet) throw new Error(`fleet is not monitored: ${token || ctx.cwd}`);
  state.monitors.delete(fleet.root);
  state.monitorSnapshots.delete(fleet.root);
  state.monitorBaselines.delete(fleet.root);
  state.monitorEvents.delete(fleet.root);
  state.lastError = undefined;
  appendMonitorEntry(pi, fleet, "detach");
  if (state.monitors.size === 0) stopMonitorTimer();
  renderWidget(ctx);
  ctx.ui.notify(`Stopped monitoring ${fleet.fleetId}`, "info");
}

async function monitorStatus(pi: ExtensionAPI, ctx: ExtensionContext): Promise<void> {
  await refreshMonitors(pi, false);
  renderWidget(ctx);
  ctx.ui.notify(state.monitors.size > 0 ? [...state.monitors.values()].map((fleet) => fleet.fleetId).join(", ") : "No fleets monitored", "info");
}

type SessionFleet = { fleet: FleetRef; mode: "mind" | "monitor" };

type PreflightRecord = {
  fleet: FleetRef;
  mode: "mind" | "monitor";
  posture: string;
  baseline: JsonObject;
  snapshot: Snapshot;
  externalLoop?: ExternalLoop;
  recommendations: string[];
};

function sessionFleets(id?: string): SessionFleet[] {
  const result: SessionFleet[] = [];
  const seen = new Set<string>();
  const add = (fleet: FleetRef, mode: "mind" | "monitor") => {
    if (id && fleet.fleetId !== id && fleet.root !== resolve(id)) return;
    if (seen.has(fleet.root)) return;
    seen.add(fleet.root);
    result.push({ fleet, mode });
  };
  for (const fleet of state.attachments.values()) add(fleet, "mind");
  for (const fleet of state.monitors.values()) add(fleet, "monitor");
  return result;
}

function resolveFleetInput(root: string | undefined, fleetId: string | undefined): string {
  if (root?.trim()) return root.trim();
  if (fleetId) {
    const current = state.candidate;
    if (current?.fleetId === fleetId) return current.root;
    const existing = sessionFleets(fleetId)[0];
    if (existing) return existing.fleet.root;
  }
  throw new Error("provide a fleet root or a fleet ID visible in the current session");
}

function preflightRecommendations(snapshot: Snapshot, baseline: JsonObject): string[] {
  const recommendations: string[] = [];
  const operator = snapshot.operator as JsonObject | undefined;
  const mind = snapshot.mind as JsonObject | undefined;
  const posture = compactState((snapshot.fleet_posture as JsonObject | undefined)?.mode ?? "unknown");
  const operatorOpen = numeric(operator?.open_count);
  const operatorToMind = numeric(operator?.to_mind_count);
  const stewardTripped = (snapshot.steward as JsonObject | undefined)?.tripped === true;
  const woundDown = (baseline.mind_loop as JsonObject | undefined)?.state === "wound_up";
  const stoppedActionableHands = Object.entries(snapshot.hands ?? {})
    .filter(([, row]) => numeric(row.actionable) > 0 && roleGlyph(row).state === "stopped")
    .map(([name]) => name);

  if (operatorOpen > 0) recommendations.push("resolve operator backlog before launch");
  if (operatorToMind > 0) recommendations.push("absorb operator-to-Mind feedback first");
  if (stewardTripped) recommendations.push("recover tripped steward before launch");
  if (woundDown) recommendations.push("review wound-down state");
  if (posture === "standby" && stoppedActionableHands.length > 0) {
    recommendations.push("select an explicit standby lane before waking stopped Hands");
  } else if (posture === "dormant" && stoppedActionableHands.length > 0) {
    recommendations.push("reactivate Fleet posture before waking stopped Hands");
  } else if (posture !== "growth" && stoppedActionableHands.length > 0) {
    recommendations.push("confirm Fleet posture before waking stopped Hands");
  } else if (!operatorOpen && !operatorToMind && !stewardTripped && !woundDown) {
    for (const name of stoppedActionableHands) recommendations.push(`start/wake ${name}`);
  }
  for (const [name, row] of Object.entries(snapshot.heads ?? {})) {
    if (row.sweep_due === true) recommendations.push(`run due ${name} sweep`);
  }
  if (numeric(mind?.inbox_unread) > 0) recommendations.push("review Mind inbox");
  if (recommendations.length === 0) recommendations.push("no immediate launch blocker detected");
  return recommendations;
}

async function runPreflight(pi: ExtensionAPI, selected?: string): Promise<PreflightRecord[]> {
  const fleets = sessionFleets(selected);
  if (fleets.length === 0) throw new Error(selected ? `fleet is not attached or monitored: ${selected}` : "no fleets are attached or monitored");
  const records: PreflightRecord[] = [];
  for (const { fleet, mode } of fleets) {
    let snapshot: Snapshot;
    let baseline: JsonObject;
    if (mode === "monitor") {
      await refreshMonitor(pi, fleet, false);
      snapshot = state.monitorSnapshots.get(fleet.root) ?? await readSnapshot(pi, fleet, true);
      baseline = state.monitorBaselines.get(fleet.root) ?? await readBaseline(pi, fleet);
    } else {
      snapshot = await refreshFleet(pi, fleet, false, true);
      baseline = state.baselines.get(fleet.root) ?? await readBaseline(pi, fleet);
    }
    records.push({
      fleet,
      mode,
      posture: compactState((snapshot.fleet_posture as JsonObject | undefined)?.mode ?? "unknown"),
      baseline,
      snapshot,
      externalLoop: state.externalLoops.get(fleet.root),
      recommendations: preflightRecommendations(snapshot, baseline),
    });
  }
  renderWidget(state.ctx);
  return records;
}

function preflightDetails(records: PreflightRecord[]): JsonObject {
  return {
    fleets: records.map(({ fleet, mode, posture, baseline, snapshot, externalLoop, recommendations }) => ({
      fleet,
      mode,
      posture,
      cycle: baselineCycle(baseline),
      baseline: {
        last_cycle_at: baseline.last_cycle_at,
        last_cycle_summary: baselineSummary(baseline),
        mind_loop: baseline.mind_loop,
        steward: baseline.steward,
        operational_pauses: baseline.operational_pauses,
      },
      snapshot: safeSnapshot(snapshot),
      external_loop: externalLoop,
      recommendations,
    })),
  };
}

function preflightText(records: PreflightRecord[]): string {
  return records.map(({ fleet, mode, posture, baseline, snapshot, recommendations }) => {
    const counts = preflightCounts(snapshot);
    const signals = (snapshot.signals ?? []).slice(0, 6).join(", ") || "none";
    return `${fleet.fleetId} mode=${mode} posture=${posture} cycle=${baselineCycle(baseline)} work=${counts.actionable} mail=${counts.mail} operator-needs=${counts.needs} pending-rtm=${counts.rtm} signals=${signals} recommendations=${recommendations.join("; ")}`;
  }).join("\n");
}

async function startMonitor(pi: ExtensionAPI, interval?: string): Promise<void> {
  if (state.monitors.size === 0) throw new Error("attach at least one monitor first");
  if (interval) state.monitorIntervalSec = parseDuration(interval);
  await refreshMonitors(pi, false);
  startMonitorTimer(pi);
  renderWidget(state.ctx);
}

async function updateMonitor(pi: ExtensionAPI, interval: string): Promise<void> {
  if (state.monitors.size === 0) throw new Error("attach at least one monitor first");
  state.monitorIntervalSec = parseDuration(interval);
  await refreshMonitors(pi, false);
  startMonitorTimer(pi);
  renderWidget(state.ctx);
}

async function detach(pi: ExtensionAPI, ctx: ExtensionContext, input: string): Promise<void> {
  const token = input.trim();
  const fleet = [...state.attachments.values()].find((item) => item.root === resolve(token) || item.fleetId === token) ??
    (token === "." || token === "" ? state.attachments.get(resolve(ctx.cwd)) : undefined);
  if (!fleet) throw new Error(`fleet is not attached: ${token || ctx.cwd}`);
  const baseline = await readBaseline(pi, fleet);
  const owner = (baseline.mind_session as JsonObject | undefined)?.label;
  const label = sessionLabel(ctx);
  if (owner && owner !== label) throw new Error(`${fleet.fleetId} is attached to another Mind session (${owner})`);
  const steward = baseline.steward as JsonObject | undefined;
  if (steward?.armed === true) {
    await pi.exec("bash", [STEWARD_SCRIPT, "disarm", "--project", fleet.root, "--fleet", fleet.fleetId], { timeout: 20_000 });
  }
  await execJson(pi, "python3", [
    BASELINE_SCRIPT, "bump", "--project", fleet.root, "--fleet", fleet.fleetId,
    "--summary", `pi fleet detach: ${label}`, "--acted", "--detach",
  ], undefined, 20_000);
  stopMailWakeSocket(fleet);
  state.attachments.delete(fleet.root);
  state.snapshots.delete(fleet.root);
  state.baselines.delete(fleet.root);
  state.externalLoops.delete(fleet.root);
  state.lastError = undefined;
  appendAttachmentEntry(pi, fleet, "detach");
  if (state.attachments.size === 0) {
    stopTimers();
    saveLoopIntent(pi, false);
  } else if (state.scheduler.isRunning()) {
    startConfiguredMailWakeSocket(pi);
  }
  renderWidget(ctx);
  ctx.ui.notify(`Detached ${fleet.fleetId}`, "info");
}

async function resumeLoop(pi: ExtensionAPI, intent: LoopEntry | undefined): Promise<void> {
  if (!intent?.running || state.attachments.size === 0) return;
  const activeExternal = [...state.externalLoops.entries()].filter(([, loop]) => loop.running !== false);
  if (activeExternal.length > 0) {
    const uncertain = activeExternal.some(([, loop]) => loop.running !== true);
    state.lastError = uncertain
      ? `cannot restore internal loop: external fleet-loop.py state is uncertain for ${activeExternal.map(([root]) => root).join(", ")}`
      : `internal loop not restored: external fleet-loop.py is running for ${activeExternal.map(([root]) => root).join(", ")}`;
    return;
  }
  state.lastError = undefined;
  startTimers(pi, intent.intervalSec);
}

async function startLoop(pi: ExtensionAPI, interval?: string): Promise<void> {
  if (state.attachments.size === 0) throw new Error("attach at least one fleet first");
  const requested = interval ? parseDuration(interval) : state.scheduler.getIntervalSec();
  // Refresh external scheduler state immediately before creating our timer. A
  // stale widget must never be enough to permit a duplicate loop.
  await refreshAll(pi, false);
  const activeExternal = [...state.externalLoops.entries()].filter(([, loop]) => loop.running !== false);
  if (activeExternal.length > 0) {
    const uncertain = activeExternal.some(([, loop]) => loop.running !== true);
    throw new Error(uncertain
      ? `cannot verify external fleet-loop.py state for ${activeExternal.map(([root]) => root).join(", ")}`
      : `external fleet-loop.py already running for ${activeExternal.map(([root]) => root).join(", ")}`);
  }
  state.lastError = undefined;
  startTimers(pi, requested);
  saveLoopIntent(pi, true);
  queueCycle(pi, "loop start");
}

async function updateLoop(pi: ExtensionAPI, interval: string): Promise<void> {
  if (!state.scheduler.isRunning()) throw new Error("internal Fleet loop is not running");
  updateTimers(pi, parseDuration(interval));
  saveLoopIntent(pi, true);
  renderWidget(state.ctx!);
}

async function loopStatus(pi: ExtensionAPI): Promise<JsonObject> {
  await refreshAll(pi, false);
  return {
    running: state.scheduler.isRunning(),
    interval_sec: state.scheduler.getIntervalSec(),
    attached: [...state.attachments.values()],
    external_loops: Object.fromEntries([...state.externalLoops.entries()].map(([root, loop]) => [root, loop])),
    started_at: state.startedAt,
    last_cycle_at: state.lastCycleAt,
    last_poll_at: state.lastPollAt,
    error: state.lastError,
  };
}

function summaryContent(text: string, details: JsonObject): { content: { type: "text"; text: string }[]; details: JsonObject } {
  return { content: [{ type: "text", text }], details };
}

function attachedFleet(id: string | undefined): FleetRef[] {
  const fleets = [...state.attachments.values()];
  if (!id) return fleets;
  const fleet = fleets.find((item) => item.fleetId === id || item.root === resolve(id));
  return fleet ? [fleet] : [];
}

type FleetCompletion = { value: string; label: string; description: string };

function fleetArgumentCompletions(prefix: string): FleetCompletion[] | null {
  const completions: FleetCompletion[] = [
    { value: "status", label: "status", description: "Show attached fleets and loop state" },
    { value: "list", label: "list", description: "List attached and monitored fleets" },
    { value: "attach .", label: "attach .", description: "Attach the current Fleet as Mind" },
    { value: "attach --monitor .", label: "attach --monitor .", description: "Monitor the current Fleet read-only" },
    { value: "attach --takeover .", label: "attach --takeover .", description: "Request confirmed Mind takeover" },
    { value: "monitor status", label: "monitor status", description: "Show read-only monitor state" },
    { value: "monitor start 60s", label: "monitor start 60s", description: "Start monitor refreshes" },
    { value: "monitor update 60s", label: "monitor update 60s", description: "Change monitor refresh cadence" },
    { value: "monitor stop", label: "monitor stop", description: "Stop monitor refreshes" },
    { value: "compact", label: "compact", description: "Show one summary line per Fleet" },
    { value: "expand", label: "expand", description: "Expand every Fleet detail panel" },
    { value: "refresh", label: "refresh", description: "Refresh canonical Fleet observations" },
    { value: "start 5m", label: "start 5m", description: "Start the Pi-owned Mind loop" },
    { value: "update 5m", label: "update 5m", description: "Change the Pi-owned loop cadence" },
    { value: "stop", label: "stop", description: "Stop the Pi-owned Mind loop" },
    { value: "loop status", label: "loop status", description: "Inspect the Pi-owned Mind loop" },
    { value: "loop start 5m", label: "loop start 5m", description: "Start the Pi-owned Mind loop" },
    { value: "loop update 5m", label: "loop update 5m", description: "Change the Pi-owned loop cadence" },
    { value: "loop stop", label: "loop stop", description: "Stop the Pi-owned Mind loop" },
  ];
  const sessionFleetIds = [...new Set(sessionFleets().map(({ fleet }) => fleet.fleetId))].sort();
  for (const fleetId of sessionFleetIds) {
    completions.push(
      { value: `focus ${fleetId}`, label: `focus ${fleetId}`, description: "Expand this Fleet and compact the rest" },
      { value: `preflight ${fleetId}`, label: `preflight ${fleetId}`, description: "Run a read-only operational preflight" },
      { value: `prepare ${fleetId}`, label: `prepare ${fleetId}`, description: "Prepare a read-only launch assessment" },
    );
  }
  for (const fleet of [...state.attachments.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId))) {
    completions.push({ value: `detach ${fleet.fleetId}`, label: `detach ${fleet.fleetId}`, description: "Detach this Mind Fleet" });
  }
  for (const fleet of [...state.monitors.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId))) {
    completions.push({ value: `monitor detach ${fleet.fleetId}`, label: `monitor detach ${fleet.fleetId}`, description: "Stop monitoring this Fleet" });
  }
  const matches = completions.filter(({ value }) => value.startsWith(prefix));
  return matches.length > 0 ? matches : null;
}

export default function (pi: ExtensionAPI): void {
  pi.registerCommand("fleet", {
    description: "Inspect and control explicitly attached Fleet roots",
    getArgumentCompletions: fleetArgumentCompletions,
    handler: async (args, ctx) => {
      state.ctx = ctx;
      const parts = args.trim().split(/\s+/).filter(Boolean);
      const action = parts.shift() ?? "status";
      try {
        if (action === "attach") {
          const monitor = parts[0] === "--monitor";
          const takeover = parts[0] === "--takeover";
          if (monitor) {
            parts.shift();
            await monitorAttach(pi, ctx, parts.join(" "));
          } else {
            if (takeover) parts.shift();
            await attach(pi, ctx, parts.join(" "), takeover);
          }
        }
        else if (action === "detach") await detach(pi, ctx, parts.join(" "));
        else if (action === "monitor") {
          const monitorAction = parts.shift() ?? "status";
          if (monitorAction === "attach") await monitorAttach(pi, ctx, parts.join(" "));
          else if (monitorAction === "detach") await monitorDetach(pi, ctx, parts.join(" "));
          else if (monitorAction === "start") await startMonitor(pi, parts[0]);
          else if (monitorAction === "update") await updateMonitor(pi, parts[0] ?? "");
          else if (monitorAction === "stop") {
            stopMonitorTimer();
            renderWidget(ctx);
          } else if (monitorAction === "status") await monitorStatus(pi, ctx);
          else throw new Error(`unknown monitor action: ${monitorAction}`);
        }
        else if (action === "compact") {
          setView(pi, "compact");
          ctx.ui.notify("Fleet panel compacted", "info");
        }
        else if (action === "expand") {
          setView(pi, "expanded");
          ctx.ui.notify("Fleet panel expanded", "info");
        }
        else if (action === "focus") {
          const fleetId = parts[0];
          if (!fleetId) throw new Error("usage: /fleet focus <fleet-id>");
          const fleet = sessionFleets(fleetId)[0];
          if (!fleet) throw new Error(`fleet is not attached or monitored: ${fleetId}`);
          setView(pi, "focus", fleet.fleet.fleetId);
          ctx.ui.notify(`Focused ${fleet.fleet.fleetId}; other fleets compacted`, "info");
        }
        else if (action === "preflight" || action === "prepare") {
          const records = await runPreflight(pi, parts[0]);
          ctx.ui.notify(`${action}:\n${preflightText(records)}`, "info");
        }
        else if (action === "list" || action === "status" || action === "refresh") {
          if (action === "refresh") await refreshAll(pi, false);
          renderWidget(ctx);
          const names = [
            ...[...state.attachments.values()].map((fleet) => `Mind:${fleet.fleetId}`),
            ...[...state.monitors.values()].map((fleet) => `Monitor:${fleet.fleetId}`),
          ];
          ctx.ui.notify(names.length > 0 ? names.join(", ") : "No fleets attached or monitored", "info");
        } else if (action === "start") await startLoop(pi, parts[0]);
        else if (action === "update") await updateLoop(pi, parts[0] ?? "");
        else if (action === "stop") {
          stopTimers();
          saveLoopIntent(pi, false);
          renderWidget(ctx);
          ctx.ui.notify("Internal Fleet loop stopped", "info");
        } else if (action === "loop") {
          const loopAction = parts.shift() ?? "status";
          if (loopAction === "start") await startLoop(pi, parts[0]);
          else if (loopAction === "update") await updateLoop(pi, parts[0] ?? "");
          else if (loopAction === "stop") {
            stopTimers();
            saveLoopIntent(pi, false);
          }
          else if (loopAction !== "status") throw new Error(`unknown loop action: ${loopAction}`);
          renderWidget(ctx);
        } else {
          throw new Error(`unknown action: ${action}; use attach, detach, monitor, compact, expand, focus, preflight, prepare, list, refresh, start, update, or stop`);
        }
      } catch (error) {
        state.lastError = error instanceof Error ? error.message : String(error);
        renderWidget(ctx);
        ctx.ui.notify(state.lastError, "error");
      }
    },
  });

  pi.registerTool({
    name: "fleet_attach",
    label: "Fleet Attach",
    description: "Attach a Fleet as the current Mind or as a read-only monitor. Mind attachment may update the canonical advisory baseline lock; monitor attachment never touches Fleet state.",
    promptSnippet: "Attach a Fleet as Mind or read-only monitor",
    parameters: Type.Object({
      root: Type.Optional(Type.String({ description: "Fleet project root containing .vivi/fleet.json" })),
      fleet_id: Type.Optional(Type.String({ description: "Known fleet ID when its root is the current candidate or session attachment" })),
      mode: Type.Optional(Type.Union([Type.Literal("mind"), Type.Literal("monitor")])),
      takeover: Type.Optional(Type.Boolean({ description: "Request confirmed takeover of a foreign Mind lock; never assume this" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      state.ctx = ctx;
      const root = resolveFleetInput(params.root, params.fleet_id);
      if (params.mode === "monitor") await monitorAttach(pi, ctx, root);
      else await attach(pi, ctx, root, params.takeover === true);
      const fleet = inspectFleet(root);
      return summaryContent(
        `${params.mode === "monitor" ? "Monitoring" : "Attached Mind"} ${fleet?.fleetId ?? params.fleet_id ?? root}`,
        { root, fleet_id: fleet?.fleetId, mode: params.mode ?? "mind", read_only: params.mode === "monitor" },
      );
    },
  });

  pi.registerTool({
    name: "fleet_detach",
    label: "Fleet Detach",
    description: "Detach the current Mind or stop a read-only monitor. Mind detachment updates the canonical baseline; monitor detachment only changes Pi session state.",
    promptSnippet: "Detach a Mind or read-only Fleet monitor",
    parameters: Type.Object({
      root: Type.Optional(Type.String()),
      fleet_id: Type.Optional(Type.String()),
      mode: Type.Optional(Type.Union([Type.Literal("mind"), Type.Literal("monitor")])),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      state.ctx = ctx;
      const root = resolveFleetInput(params.root, params.fleet_id);
      const mode = params.mode ?? (state.monitors.has(resolve(root)) && !state.attachments.has(resolve(root)) ? "monitor" : "mind");
      if (mode === "monitor") {
        await monitorDetach(pi, ctx, root);
      } else {
        const ok = await ctx.ui.confirm("Detach Fleet Mind?", `Detach Mind control from ${params.fleet_id ?? root}? This updates the Fleet baseline.`);
        if (!ok) throw new Error("Mind detach cancelled");
        await detach(pi, ctx, root);
      }
      return summaryContent(`Detached ${params.fleet_id ?? root} (${mode})`, { root, mode });
    },
  });

  pi.registerTool({
    name: "fleet_preflight",
    label: "Fleet Preflight",
    description: "Run a read-only Fleet-specific preflight for explicitly attached or monitored fleets. It inspects config, baseline, Vivi, runtimes, posture, blockers, and launch hazards without modifying Fleet state or waking a Mind.",
    promptSnippet: "Run a read-only Fleet preflight",
    parameters: Type.Object({ fleet_id: Type.Optional(Type.String()) }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      state.ctx = ctx;
      const records = await runPreflight(pi, params.fleet_id);
      return summaryContent(preflightText(records), preflightDetails(records));
    },
  });

  pi.registerTool({
    name: "fleet_prepare",
    label: "Fleet Prepare",
    description: "Prepare a read-only launch assessment after Fleet preflight. Returns recommended runtime, operator, posture, and tasking follow-ups without starting processes or filing work.",
    promptSnippet: "Prepare a read-only Fleet launch assessment",
    parameters: Type.Object({ fleet_id: Type.Optional(Type.String()) }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      state.ctx = ctx;
      const records = await runPreflight(pi, params.fleet_id);
      return summaryContent(`Launch assessment:\n${preflightText(records)}`, {
        ...preflightDetails(records),
        side_effects: "none",
        next_step: "operator confirmation required before any Fleet launch action",
      });
    },
  });

  pi.registerTool({
    name: "fleet_sensors",
    label: "Fleet Sensors",
    description: "Read canonical Fleet sensor snapshots for explicitly attached fleets. This is read-only.",
    promptSnippet: "Read canonical sensors for attached Fleet roots",
    parameters: Type.Object({ fleet_id: Type.Optional(Type.String()) }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      state.ctx = ctx;
      const fleets = attachedFleet(params.fleet_id);
      if (fleets.length === 0) throw new Error(params.fleet_id ? `fleet is not attached: ${params.fleet_id}` : "no fleets are attached");
      const results: JsonObject[] = [];
      for (const fleet of fleets) {
        const snapshot = await refreshFleet(pi, fleet, false);
        results.push({ fleet: fleet, snapshot: safeSnapshot(snapshot) });
      }
      const text = results.map((item) => snapshotSummary(item.fleet as FleetRef, item.snapshot as Snapshot)).join("\n");
      return summaryContent(text, { fleets: results });
    },
  });

  pi.registerTool({
    name: "fleet_board",
    label: "Fleet Board",
    description: "Read board/task/need/mail and integration observations from explicitly attached fleets. This is read-only.",
    promptSnippet: "Read Fleet board and integration signals",
    parameters: Type.Object({ fleet_id: Type.Optional(Type.String()) }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      state.ctx = ctx;
      const fleets = attachedFleet(params.fleet_id);
      if (fleets.length === 0) throw new Error(params.fleet_id ? `fleet is not attached: ${params.fleet_id}` : "no fleets are attached");
      const boards = [];
      for (const fleet of fleets) {
        const snapshot = await refreshFleet(pi, fleet, false);
        const safe = safeSnapshot(snapshot);
        boards.push({ fleet: fleet.fleetId, operator: safe.operator, mind: safe.mind, hands: safe.hands, heads: safe.heads, integration: safe.integration, signals: safe.signals });
      }
      return summaryContent(boards.map((board) => `${board.fleet}: signals=${(board.signals as string[] | undefined)?.length ?? 0} pending_rtm=${(board.integration as JsonObject | undefined)?.pending_rtm_count ?? 0}`).join("\n"), { fleets: boards });
    },
  });

  pi.registerTool({
    name: "fleet_runtime",
    label: "Fleet Runtime",
    description: "Read configured Fleet process/runtime observations for explicitly attached fleets. This is read-only.",
    promptSnippet: "Read Fleet runtime and pane health",
    parameters: Type.Object({ fleet_id: Type.Optional(Type.String()) }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      state.ctx = ctx;
      const fleets = attachedFleet(params.fleet_id);
      if (fleets.length === 0) throw new Error(params.fleet_id ? `fleet is not attached: ${params.fleet_id}` : "no fleets are attached");
      const runtimes = [];
      for (const fleet of fleets) {
        const snapshot = await refreshFleet(pi, fleet, false);
        const roles = (group: Record<string, JsonObject> | undefined) => Object.fromEntries(Object.entries(group ?? {}).map(([role, row]) => [role, safeRuntime(row.runtime)]));
        runtimes.push({ fleet: fleet.fleetId, hands: roles(snapshot.hands), heads: roles(snapshot.heads), steward: safeRuntime(snapshot.steward?.runtime), external_loop: state.externalLoops.get(fleet.root) });
      }
      return summaryContent(runtimes.map((runtime) => `${runtime.fleet}: runtime observations available`).join("\n"), { fleets: runtimes });
    },
  });

  pi.registerTool({
    name: "fleet_loop",
    label: "Fleet Loop",
    description: "Inspect or control the Pi-owned internal Fleet cycle for explicitly attached fleets. It never arms a steward and refuses an existing external loop.",
    promptSnippet: "Inspect or control the Pi-owned Fleet cycle",
    parameters: Type.Object({
      action: Type.Union([Type.Literal("status"), Type.Literal("start"), Type.Literal("update"), Type.Literal("stop")]),
      interval: Type.Optional(Type.String({ description: "Duration such as 5m or 300s; minimum 60s" })),
    }),
    async execute(_toolCallId, params, _signal, _onUpdate, ctx) {
      state.ctx = ctx;
      if (params.action === "start") await startLoop(pi, params.interval);
      else if (params.action === "update") await updateLoop(pi, params.interval ?? "");
      else if (params.action === "stop") {
        stopTimers();
        saveLoopIntent(pi, false);
      }
      const details = await loopStatus(pi);
      renderWidget(state.ctx!);
      return summaryContent(`Fleet loop ${details.running ? "running" : "stopped"} interval=${details.interval_sec}s attached=${(details.attached as FleetRef[]).map((fleet) => fleet.fleetId).join(",") || "none"}`, details);
    },
  });

  pi.on("session_start", async (_event, ctx) => {
    state.ctx = ctx;
    state.candidate = inspectFleet(ctx.cwd);
    state.snapshots.clear();
    state.monitorSnapshots.clear();
    state.monitorBaselines.clear();
    state.monitorEvents.clear();
    state.externalLoops.clear();
    state.lastError = undefined;
    startUiTimer();
    restoreAttachments(ctx);
    restoreMonitors(ctx);
    restoreView(ctx);
    restoreMailWakeState(ctx);
    const loopIntent = restoreLoopIntent(ctx);
    renderWidget(ctx);
    if (state.attachments.size > 0) {
      await refreshAll(pi, false);
      await resumeLoop(pi, loopIntent);
    }
    if (state.monitors.size > 0) {
      await refreshMonitors(pi, false);
      startMonitorTimer(pi);
    }
  });

  pi.on("agent_settled", () => {
    onAgentSettled(pi);
  });

  pi.on("session_shutdown", () => {
    if (state.scheduler.isRunning()) saveLoopIntent(pi, true);
    stopTimers();
    stopMonitorTimer();
    stopMailWakeSockets();
    state.mailWakeTimer = clearMailWakeTimerHandle(state.mailWakeTimer);
    stopUiTimer();
    state.ctx = undefined;
    state.snapshots.clear();
    state.monitorSnapshots.clear();
    state.monitorBaselines.clear();
    state.monitorEvents.clear();
    state.externalLoops.clear();
  });
}
