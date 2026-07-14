import { readFileSync, existsSync } from "node:fs";
import { hostname } from "node:os";
import { dirname, resolve } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
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

type State = {
  ctx?: ExtensionContext;
  candidate?: FleetRef;
  attachments: Map<string, FleetRef>;
  snapshots: Map<string, Snapshot>;
  externalLoops: Map<string, ExternalLoop>;
  pollTimer?: ReturnType<typeof setInterval>;
  loopTimer?: ReturnType<typeof setInterval>;
  pollInFlight: boolean;
  cycleInFlight: boolean;
  cycleQueued: boolean;
  loopRunning: boolean;
  intervalSec: number;
  startedAt?: string;
  lastCycleAt?: string;
  lastPollAt?: string;
  lastError?: string;
};

const state: State = {
  attachments: new Map(),
  snapshots: new Map(),
  externalLoops: new Map(),
  pollInFlight: false,
  cycleInFlight: false,
  cycleQueued: false,
  loopRunning: false,
  intervalSec: DEFAULT_INTERVAL_SEC,
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

function appendAttachmentEntry(pi: ExtensionAPI, fleet: FleetRef, action: "attach" | "detach"): void {
  pi.appendEntry(ATTACHMENT_ENTRY, { action, root: fleet.root, fleetId: fleet.fleetId } satisfies AttachmentEntry);
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

function roleState(role: JsonObject): string {
  const runtime = role.runtime as JsonObject | undefined;
  return compactState(runtime?.state ?? role.state ?? "unknown");
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

function cyclePayload(): string {
  const fleets = [...state.attachments.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId));
  const slugs = fleets.map((fleet) => fleet.fleetId).join(",");
  const roots = fleets.map((fleet) => `  ${fleet.fleetId}: ${fleet.root}`).join("\n");
  return `FLEET_CYCLE fleets=${slugs}\nRoots:\n${roots}`;
}

function renderWidget(ctx?: ExtensionContext): void {
  if (!ctx) return;
  const fleets = [...state.attachments.values()].sort((a, b) => a.fleetId.localeCompare(b.fleetId));
  const candidate = state.candidate && !state.attachments.has(state.candidate.root) ? state.candidate : undefined;
  if (fleets.length === 0 && !candidate) {
    ctx.ui.setWidget(WIDGET_KEY, undefined);
    ctx.ui.setStatus(STATUS_KEY, undefined);
    return;
  }

  const lines: string[] = [];
  if (fleets.length > 0) {
    const loop = state.loopRunning ? `loop ${state.intervalSec}s` : "loop off";
    lines.push(`Fleet  ${fleets.map((fleet) => fleet.fleetId).join(",")}  ${loop}`);
    for (const fleet of fleets) {
      const snapshot = state.snapshots.get(fleet.root);
      const external = state.externalLoops.get(fleet.root);
      const externalMark = external?.running ? " external-loop" : "";
      lines.push(`  ${snapshot ? snapshotSummary(fleet, snapshot) : `${fleet.fleetId} sensors=pending`}${externalMark}`);
      const signals = snapshot?.signals ?? [];
      if (signals.length > 0) lines.push(`    signals: ${signals.slice(0, 3).join(", ")}${signals.length > 3 ? ` +${signals.length - 3}` : ""}`);
    }
    if (state.lastError) lines.push(`  error: ${state.lastError}`);
  } else if (candidate) {
    lines.push(`Fleet candidate  ${candidate.fleetId}`);
    lines.push(`  ${shellSafePath(candidate.root)}`);
    lines.push("  use /fleet attach . to attach");
  }
  ctx.ui.setWidget(WIDGET_KEY, lines);
  ctx.ui.setStatus(STATUS_KEY, fleets.length > 0 ? `fleet:${fleets.map((fleet) => fleet.fleetId).join(",")}` : `fleet? ${candidate?.fleetId}`);
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

async function readSnapshot(pi: ExtensionAPI, fleet: FleetRef): Promise<Snapshot> {
  // fleet-sensors.py uses exit code 2 for a partial-but-usable snapshot.
  return await execJson(
    pi,
    "python3",
    [SENSOR_SCRIPT, "--project", fleet.root, "--fleet", fleet.fleetId, "--json"],
    undefined,
    45_000,
    [0, 2],
  ) as Snapshot;
}

async function refreshFleet(pi: ExtensionAPI, fleet: FleetRef, wakeOnChange: boolean): Promise<Snapshot> {
  const [snapshot, external] = await Promise.all([readSnapshot(pi, fleet), readExternalLoop(pi, fleet)]);
  const previous = state.snapshots.get(fleet.root);
  state.snapshots.set(fleet.root, snapshot);
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

function stopTimers(): void {
  if (state.pollTimer) clearInterval(state.pollTimer);
  if (state.loopTimer) clearInterval(state.loopTimer);
  state.pollTimer = undefined;
  state.loopTimer = undefined;
  state.loopRunning = false;
  state.cycleQueued = false;
}

function startTimers(pi: ExtensionAPI): void {
  stopTimers();
  state.loopRunning = true;
  state.startedAt ??= new Date().toISOString();
  state.pollTimer = setInterval(() => {
    void refreshAll(pi, true);
  }, POLL_INTERVAL_MS);
  state.loopTimer = setInterval(() => {
    queueCycle(pi, "scheduled cycle");
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
  state.externalLoops.delete(fleet.root);
  state.lastError = undefined;
  appendAttachmentEntry(pi, fleet, "detach");
  if (state.attachments.size === 0) stopTimers();
  renderWidget(ctx);
  ctx.ui.notify(`Detached ${fleet.fleetId}`, "info");
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
  queueCycle(pi, "loop start");
}

async function updateLoop(pi: ExtensionAPI, interval: string): Promise<void> {
  if (!state.loopRunning) throw new Error("internal Fleet loop is not running");
  state.intervalSec = parseDuration(interval);
  startTimers(pi);
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
          const takeover = parts[0] === "--takeover";
          if (takeover) parts.shift();
          await attach(pi, ctx, parts.join(" "), takeover);
        }
        else if (action === "detach") await detach(pi, ctx, parts.join(" "));
        else if (action === "list" || action === "status" || action === "refresh") {
          if (action === "refresh") await refreshAll(pi, false);
          renderWidget(ctx);
          ctx.ui.notify(state.attachments.size ? [...state.attachments.values()].map((fleet) => fleet.fleetId).join(", ") : "No fleets attached", "info");
        } else if (action === "start") await startLoop(pi, parts[0]);
        else if (action === "update") await updateLoop(pi, parts[0] ?? "");
        else if (action === "stop") {
          stopTimers();
          renderWidget(ctx);
          ctx.ui.notify("Internal Fleet loop stopped", "info");
        } else if (action === "loop") {
          const loopAction = parts.shift() ?? "status";
          if (loopAction === "start") await startLoop(pi, parts[0]);
          else if (loopAction === "update") await updateLoop(pi, parts[0] ?? "");
          else if (loopAction === "stop") stopTimers();
          else if (loopAction !== "status") throw new Error(`unknown loop action: ${loopAction}`);
          renderWidget(ctx);
        } else {
          throw new Error(`unknown action: ${action}; use attach, detach, list, refresh, start, update, or stop`);
        }
      } catch (error) {
        state.lastError = error instanceof Error ? error.message : String(error);
        renderWidget(ctx);
        ctx.ui.notify(state.lastError, "error");
      }
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
      else if (params.action === "stop") stopTimers();
      const details = await loopStatus(pi);
      renderWidget(state.ctx!);
      return summaryContent(`Fleet loop ${details.running ? "running" : "stopped"} interval=${details.interval_sec}s attached=${(details.attached as FleetRef[]).map((fleet) => fleet.fleetId).join(",") || "none"}`, details);
    },
  });

  pi.on("session_start", async (_event, ctx) => {
    state.ctx = ctx;
    state.candidate = inspectFleet(ctx.cwd);
    state.snapshots.clear();
    state.externalLoops.clear();
    state.lastError = undefined;
    restoreAttachments(ctx);
    renderWidget(ctx);
    if (state.attachments.size > 0) await refreshAll(pi, false);
  });

  pi.on("agent_settled", () => {
    onAgentSettled();
  });

  pi.on("session_shutdown", () => {
    stopTimers();
    state.ctx = undefined;
    state.snapshots.clear();
    state.externalLoops.clear();
  });
}
