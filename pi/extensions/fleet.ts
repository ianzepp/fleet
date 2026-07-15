import { readFileSync, existsSync } from "node:fs";
import { hostname } from "node:os";
import { dirname, resolve } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";
import { Type } from "typebox";

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
const WIDGET_KEY = "pi-fleet";
const STATUS_KEY = "pi-fleet";

type JsonObject = Record<string, unknown>;

type FleetRef = {
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
  loopTimer?: ReturnType<typeof setInterval>;
  uiTimer?: ReturnType<typeof setInterval>;
  pollInFlight: boolean;
  cycleInFlight: boolean;
  cycleQueued: boolean;
  loopRunning: boolean;
  intervalSec: number;
  monitorIntervalSec: number;
  viewMode: FleetViewMode;
  focusedFleetId?: string;
  startedAt?: string;
  lastCycleAt?: string;
  nextCycleAt?: number;
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
  pollInFlight: false,
  cycleInFlight: false,
  cycleQueued: false,
  loopRunning: false,
  intervalSec: DEFAULT_INTERVAL_SEC,
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
  pi.appendEntry(LOOP_ENTRY, { running, intervalSec: state.intervalSec } satisfies LoopEntry);
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

function snapshotChanged(previous: Snapshot | undefined, next: Snapshot): boolean {
  if (!previous) return false;
  return JSON.stringify({ signals: previous.signals ?? [], fingerprint: previous.fingerprint ?? {} }) !==
    JSON.stringify({ signals: next.signals ?? [], fingerprint: next.fingerprint ?? {} });
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

function roleToken(name: string, row: JsonObject, head: boolean, theme: any): string {
  const status = roleGlyph(row);
  const shortName = head ? name.replace(/^head-/, "") : name.replace(/^hand-/, "h");
  const metric = head
    ? row.sweep_due === true ? "due" : row.sweep_enabled === true ? "on" : "—"
    : String(numeric(row.actionable ?? row.tasks_open));
  const labelColor = status.state === "unknown" ? "dim" : "muted";
  return `${theme.fg(status.color, status.glyph)} ${theme.fg(labelColor, shortName)}${theme.fg("dim", `:${metric}`)}`;
}

function roleGroups(): { hands: Array<[string, JsonObject]>; heads: Array<[string, JsonObject]> } {
  const hands: Array<[string, JsonObject]> = [];
  const heads: Array<[string, JsonObject]> = [];
  for (const snapshot of state.snapshots.values()) {
    for (const [name, row] of Object.entries(snapshot.hands ?? {})) hands.push([name, row]);
    for (const [name, row] of Object.entries(snapshot.heads ?? {})) heads.push([name, row]);
  }
  return { hands, heads };
}

function panelMetrics(): { activeHands: number; totalHands: number; activeHeads: number; totalHeads: number; mail: number; needs: number; rtm: number; signals: number; actionable: number } {
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
  const { hands, heads } = roleGroups();
  return {
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
  if (mode === "mind" && state.loopRunning && state.nextCycleAt !== undefined) {
    return `next ${formatDuration(state.nextCycleAt / 1000 - Date.now() / 1000)}`;
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
  const hands = Object.values(snapshot?.hands ?? {});
  const heads = Object.values(snapshot?.heads ?? {});
  const activeHands = hands.filter((row) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length;
  const activeHeads = heads.filter((row) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length;
  const counts = snapshot ? preflightCounts(snapshot) : { actionable: 0, mail: 0, needs: 0, rtm: 0 };
  const signals = signalCount(snapshot);
  const signalText = signals > 0 ? theme.fg("warning", `!${signals}`) : theme.fg("dim", "!0");
  const external = mode === "mind" && state.externalLoops.get(fleet.root)?.running ? theme.fg("warning", " !ext") : "";
  return ` ${theme.fg("accent", "◈")} ${theme.bold(fleet.fleetId)} ${theme.fg(modeColor, modeText)} ${theme.fg(posture === "growth" ? "success" : "dim", posture)}  ${theme.fg("dim", `cycle ${baseline ? baselineCycle(baseline) : "—"}`)} · ${theme.fg("dim", `H${activeHands}/${hands.length}`)} · ${theme.fg("dim", `Hd${activeHeads}/${heads.length}`)} · ${theme.fg("dim", `work ${counts.actionable}`)} · ${theme.fg("dim", `✉${counts.mail}`)} · ${theme.fg("dim", `⚑${counts.needs}`)} · ${theme.fg("dim", `↻${counts.rtm}`)} · ${signalText} · ${theme.fg("dim", fleetNextCycle(fleet, mode, baseline))}${external}`;
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
  const { hands, heads } = { hands: Object.entries(snapshot.hands ?? {}), heads: Object.entries(snapshot.heads ?? {}) };
  const handTokens = hands.map(([name, row]) => roleToken(name, row, false, theme)).join("  ");
  const headTokens = heads.map(([name, row]) => roleToken(name, row, true, theme)).join("  ");
  const counts = preflightCounts(snapshot);
  const signalText = signalCount(snapshot) > 0 ? theme.fg("warning", `!${signalCount(snapshot)}`) : theme.fg("dim", "!0");
  lines.push(`   ${theme.fg("muted", "Hand")} ${theme.fg("dim", `${hands.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length}/${hands.length}`)}  ${handTokens || theme.fg("dim", "idle")}`);
  lines.push(`   ${theme.fg("muted", "Head")} ${theme.fg("dim", `${heads.filter(([, row]) => ACTIVE_RUNTIME_STATES.has(roleGlyph(row).state)).length}/${heads.length}`)}  ${headTokens || theme.fg("dim", "idle")}`);
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
      ? `◈ ${fleets.map((fleet) => fleet.fleetId).join(",")} · H${metrics.activeHands}/${metrics.totalHands} · Hd${metrics.activeHeads}/${metrics.totalHeads} · ✉${metrics.mail} · !${metrics.signals}${monitors.length > 0 ? ` · M${monitors.length}` : ""}`
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
  if (state.loopRunning && external.running !== false) {
    stopTimers();
    state.lastError = external.running
      ? `external fleet-loop.py detected for ${fleet.fleetId}; internal loop stopped`
      : `cannot verify external fleet-loop.py state for ${fleet.fleetId}; internal loop stopped`;
  }
  if (wakeOnChange && snapshotChanged(previous, snapshot)) queueCycle(pi, `sensor change: ${fleet.fleetId}`);
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
    if (state.ctx && (state.loopRunning || state.monitors.size > 0)) renderWidget(state.ctx);
  }, 1000);
}

function stopUiTimer(): void {
  if (state.uiTimer) clearInterval(state.uiTimer);
  state.uiTimer = undefined;
}

function stopTimers(): void {
  if (state.pollTimer) clearInterval(state.pollTimer);
  if (state.loopTimer) clearInterval(state.loopTimer);
  state.pollTimer = undefined;
  state.loopTimer = undefined;
  state.loopRunning = false;
  state.nextCycleAt = undefined;
  state.cycleQueued = false;
}

function startTimers(pi: ExtensionAPI): void {
  stopTimers();
  state.loopRunning = true;
  state.nextCycleAt = Date.now() + state.intervalSec * 1000;
  state.startedAt ??= new Date().toISOString();
  state.pollTimer = setInterval(() => {
    void refreshAll(pi, true);
  }, POLL_INTERVAL_MS);
  state.loopTimer = setInterval(() => {
    state.nextCycleAt = Date.now() + state.intervalSec * 1000;
    // Refresh immediately before scheduled delivery so the preflight is not
    // merely the last 60-second poll snapshot.
    void refreshAll(pi, false).then(() => {
      queueCycle(pi, "scheduled cycle");
      renderWidget(state.ctx);
    });
  }, state.intervalSec * 1000);
  renderWidget(state.ctx!);
}

function queueCycle(pi: ExtensionAPI, reason: string): void {
  if (!state.loopRunning || state.attachments.size === 0 || state.cycleQueued || state.cycleInFlight) return;
  const ctx = state.ctx;
  if (!ctx) return;
  state.cycleQueued = true;
  try {
    const payload = `${cyclePayload()}\n\nReason: ${reason}`;
    const delivery = ctx.isIdle() ? undefined : "followUp";
    pi.sendUserMessage(payload, delivery ? { deliverAs: delivery } : undefined);
    state.lastCycleAt = new Date().toISOString();
    state.cycleInFlight = true;
  } catch (error) {
    state.lastError = error instanceof Error ? error.message : String(error);
  } finally {
    state.cycleQueued = false;
  }
}

function onAgentSettled(): void {
  state.cycleInFlight = false;
  state.cycleQueued = false;
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
  state.attachments.delete(fleet.root);
  state.snapshots.delete(fleet.root);
  state.baselines.delete(fleet.root);
  state.externalLoops.delete(fleet.root);
  state.lastError = undefined;
  appendAttachmentEntry(pi, fleet, "detach");
  if (state.attachments.size === 0) {
    stopTimers();
    saveLoopIntent(pi, false);
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
  state.intervalSec = intent.intervalSec;
  state.lastError = undefined;
  startTimers(pi);
}

async function startLoop(pi: ExtensionAPI, interval?: string): Promise<void> {
  if (state.attachments.size === 0) throw new Error("attach at least one fleet first");
  const requested = interval ? parseDuration(interval) : state.intervalSec;
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
  state.intervalSec = requested;
  state.lastError = undefined;
  startTimers(pi);
  saveLoopIntent(pi, true);
  queueCycle(pi, "loop start");
}

async function updateLoop(pi: ExtensionAPI, interval: string): Promise<void> {
  if (!state.loopRunning) throw new Error("internal Fleet loop is not running");
  state.intervalSec = parseDuration(interval);
  startTimers(pi);
  saveLoopIntent(pi, true);
  renderWidget(state.ctx!);
}

async function loopStatus(pi: ExtensionAPI): Promise<JsonObject> {
  await refreshAll(pi, false);
  return {
    running: state.loopRunning,
    interval_sec: state.intervalSec,
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

export default function (pi: ExtensionAPI): void {
  pi.registerCommand("fleet", {
    description: "Inspect and control explicitly attached Fleet roots",
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
    onAgentSettled();
  });

  pi.on("session_shutdown", () => {
    if (state.loopRunning) saveLoopIntent(pi, true);
    stopTimers();
    stopMonitorTimer();
    stopUiTimer();
    state.ctx = undefined;
    state.snapshots.clear();
    state.monitorSnapshots.clear();
    state.monitorBaselines.clear();
    state.monitorEvents.clear();
    state.externalLoops.clear();
  });
}
