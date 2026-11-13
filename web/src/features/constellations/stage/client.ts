import { apiBase } from "../apiBase";
/*
 * Stage (presenter screen) data and controls. Live API only: there is no fixture
 * for this view, so without VITE_CONSTELLATIONS_API the page says so instead of
 * faking it. Every response is validated before use.
 */
export type Slot = "A" | "B";
export type SlotChoice = Slot | "off" | null;

export type StageCall = { callType: string; model: string; source: string; generatedAt: string; latencyMs: number };
export type StageConstellation = { name: string | null; size: number; isLooseMatch: boolean; mapSeed: string };
export type StageAnswer = { day: number; text: string; scripted: boolean };
export type StagePanel = {
  slot: Slot;
  joined: boolean;
  displayName: string | null;
  answers: StageAnswer[];
  /** What the presenter should type on this phone today, if anything. */
  toType: string | null;
  constellation: StageConstellation | null;
};
export type StageView = {
  cycle: { cycleId: string; status: string; currentDay: number } | null;
  today: { day: number; text: string } | null;
  liveDay: number;
  formation: { jobStatus: string | null; formed: boolean; eligiblePlayers: number | null };
  population: { players: number; syntheticPlayers: number; answersByDay: number[] };
  panels: StagePanel[];
  themes: { label: string; count: number; slots: Slot[] }[];
  suppressedThemes: number;
  constellations: (StageConstellation & { slots: Slot[] })[];
  calls: StageCall[];
};

export class StageError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const base = apiBase() ?? null;
export const stageAvailable = base !== null;

const rec = (v: unknown): Record<string, unknown> => (v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {});
const str = (v: unknown, max = 400): string => (typeof v === "string" ? v.slice(0, max) : "");
const num = (v: unknown, lo = 0, hi = 1_000_000): number => (typeof v === "number" && Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : 0);
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const slot = (v: unknown): Slot | null => (v === "A" || v === "B" ? v : null);
const slots = (v: unknown): Slot[] => list(v).map(slot).filter((s): s is Slot => s !== null);
const optStr = (v: unknown, max: number): string | null => (typeof v === "string" && v ? v.slice(0, max) : null);

function constellation(v: unknown): StageConstellation | null {
  if (!v || typeof v !== "object") return null;
  const o = rec(v);
  return {
    name: optStr(o.name, 80),
    size: num(o.size, 0, 500),
    isLooseMatch: o.isLooseMatch === true,
    mapSeed: str(o.mapSeed, 16).replace(/[^0-9a-f]/g, "") || "0",
  };
}

export function parseStage(value: unknown): StageView {
  const o = rec(value);
  const cycle = o.cycle && typeof o.cycle === "object" ? rec(o.cycle) : null;
  const today = o.today && typeof o.today === "object" ? rec(o.today) : null;
  const formation = rec(o.formation);
  const population = rec(o.population);
  const byDay = list(population.answersByDay).map((n) => num(n));
  return {
    cycle: cycle ? { cycleId: str(cycle.cycleId, 80), status: str(cycle.status, 20), currentDay: num(cycle.currentDay, 1, 5) } : null,
    today: today ? { day: num(today.day, 1, 5), text: str(today.text, 300) } : null,
    liveDay: num(o.liveDay, 1, 5) || 5,
    formation: {
      jobStatus: typeof formation.jobStatus === "string" ? str(formation.jobStatus, 20) : null,
      formed: formation.formed === true,
      eligiblePlayers: typeof formation.eligiblePlayers === "number" ? num(formation.eligiblePlayers) : null,
    },
    population: {
      players: num(population.players),
      syntheticPlayers: num(population.syntheticPlayers),
      answersByDay: [0, 1, 2, 3, 4].map((i) => byDay[i] ?? 0),
    },
    panels: (["A", "B"] as Slot[]).map((s) => {
      const p = rec(list(o.panels).find((x) => rec(x).slot === s));
      return {
        slot: s,
        joined: p.joined === true,
        displayName: optStr(p.displayName, 40),
        answers: list(p.answers)
          .map((a) => ({ day: num(rec(a).day, 1, 5), text: str(rec(a).text, 600), scripted: rec(a).scripted === true }))
          .filter((a) => a.text),
        toType: optStr(p.toType, 400),
        constellation: constellation(p.constellation),
      };
    }),
    themes: list(o.themes)
      .map((t) => ({ label: str(rec(t).label, 80), count: num(rec(t).count), slots: slots(rec(t).slots) }))
      .filter((t) => t.label),
    suppressedThemes: num(o.suppressedThemes),
    constellations: list(o.constellations).flatMap((c) => {
      const parsed = constellation(c);
      return parsed ? [{ ...parsed, slots: slots(rec(c).slots) }] : [];
    }),
    calls: list(o.calls)
      .map((c) => {
        const e = rec(c);
        return { callType: str(e.callType, 4), model: str(e.model, 40), source: str(e.source, 12), generatedAt: str(e.generatedAt, 40), latencyMs: num(e.latencyMs) };
      })
      .filter((c) => c.callType && c.generatedAt),
  };
}

async function request(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<unknown> {
  if (!base) throw new StageError(0, "The live API is not configured.");
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["Idempotency-Key"] = crypto.randomUUID();
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, { method, headers, credentials: "include", signal, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch (error) {
    if ((error as Error)?.name === "AbortError") throw error;
    throw new StageError(0, "The server could not be reached.");
  }
  const json: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new StageError(response.status, str(rec(rec(json).error).message, 200) || "The request failed.");
  return json;
}

const choice = (v: unknown): SlotChoice => (v === "A" || v === "B" || v === "off" ? v : null);

export const fetchStage = async (signal?: AbortSignal): Promise<StageView> => parseStage(await request("GET", "/operator/stage", undefined, signal));
export const startWeek = async (): Promise<StageView> => parseStage(await request("POST", "/operator/stage/start"));
export const nextStep = async (): Promise<StageView> => parseStage(await request("POST", "/operator/stage/next"));
export const skipPhone = async (slot: Slot): Promise<StageView> => parseStage(await request("POST", "/operator/stage/skip", { slot }));
export const redetectPhones = async (): Promise<StageView> => parseStage(await request("POST", "/operator/stage/phones/reset"));
export const fetchMySlot = async (signal?: AbortSignal): Promise<SlotChoice> => choice(rec(await request("GET", "/me/stage", undefined, signal)).slot);
export const chooseSlot = async (value: SlotChoice): Promise<SlotChoice> => choice(rec(await request("POST", "/me/stage", { slot: value })).slot);
