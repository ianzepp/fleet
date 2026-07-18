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
