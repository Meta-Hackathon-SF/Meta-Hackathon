/** Shapes produced by server/matching (Rishi). Ids only; never answer text. */
export interface FormationDebugData {
  baselineGroups: string[][];
  museGroups: string[][];
  agreements: number;
  splitByBaseline: [string, string][];
}

export interface FormationEvidence {
  callType: "M3" | "M4" | "M5" | "M8";
  model: string;
  source: "live" | "replay";
  latencyMs: number;
}

export interface FormationDebugProps {
  data: FormationDebugData;
  evidence: FormationEvidence[];
  totalMs: number;
  usedFallback: boolean;
}

/** Runtime check for data arriving over the network. Returns null when invalid. */
export function parseFormationDebug(value: unknown): FormationDebugData | null {
  if (typeof value !== "object" || value === null) return null;
  const v = value as Record<string, unknown>;
  const isGroups = (g: unknown): g is string[][] =>
    Array.isArray(g) && g.every((x) => Array.isArray(x) && x.every((y) => typeof y === "string"));
  const isPairs = (p: unknown): p is [string, string][] =>
    Array.isArray(p) &&
    p.every((x) => Array.isArray(x) && x.length === 2 && x.every((y) => typeof y === "string"));
  if (!isGroups(v.baselineGroups) || !isGroups(v.museGroups)) return null;
  if (typeof v.agreements !== "number" || !isPairs(v.splitByBaseline)) return null;
  return {
    baselineGroups: v.baselineGroups,
    museGroups: v.museGroups,
    agreements: v.agreements,
    splitByBaseline: v.splitByBaseline,
  };
}
