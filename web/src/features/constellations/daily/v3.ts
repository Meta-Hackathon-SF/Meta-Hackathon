/*
 * v3 daily shapes (owner: Will). PENDING contract 3.0.0 (D012, docs/PRD-v3.md S5, S6, S15).
 *
 * contracts/protocol.ts is still 2.1.0, so these are LOCAL mirrors of the PRD-v3
 * type sketch, not shared wire types. When Rishi lands 3.0.0, replace them with
 * type-only imports from contracts/protocol.ts and keep the validators below.
 * TypeScript types are not validation: every server response is checked here.
 */
import { ClientError, type CycleDay, type MuseCallEvidence } from "./client";

// ---- day colors (one per weekday, used on every screen) ---------------------
export type DayColorId = "blue" | "teal" | "green" | "amber" | "rose";

export interface DayColor {
  id: DayColorId;
  /** Human name, so color is never the only cue. */
  name: string;
  /** Stars, dots and lines. Meets 3:1 against white for graphics. */
  hex: string;
  /** Text on white. Meets 4.5:1. */
  ink: string;
  /** Soft background tint. */
  soft: string;
}

export const DAY_COLORS: Record<CycleDay, DayColor> = {
  1: { id: "blue", name: "Blue", hex: "#1877f2", ink: "#0b5bd3", soft: "#e7f3ff" },
  2: { id: "teal", name: "Teal", hex: "#0e9f9a", ink: "#0a7570", soft: "#e0f6f5" },
  3: { id: "green", name: "Green", hex: "#31a24c", ink: "#1f7a36", soft: "#e6f4e9" },
  4: { id: "amber", name: "Amber", hex: "#e8a317", ink: "#8a5a00", soft: "#fdf2dc" },
  5: { id: "rose", name: "Rose", hex: "#e4416b", ink: "#b42a4f", soft: "#fde8ee" },
};

const COLOR_IDS = Object.values(DAY_COLORS).map((c) => c.id);

/** CSS custom properties for a day's color, for `style={dayStyle(day)}`. */
export function dayStyle(day: CycleDay): Record<string, string> {
  const c = DAY_COLORS[day];
  return { "--day": c.hex, "--day-ink": c.ink, "--day-soft": c.soft };
}

// ---- S5 daily constellation reveal -------------------------------------------
export type Brightness = "bright" | "mid" | "faint";

export interface DailyConstellation {
  constellationId: string;
  /** Week-randomized star indices, never player ids. Includes myStarIndex. */
  starIndices: number[];
  brightness: Brightness;
  /** Muse-written, guarded; only meaningful with 3 or more members. */
  sharedMeaning?: string | null;
  /** Members in this constellation, you included. */
  memberCount?: number;
  /** True when sharedMeaning came from the deterministic fallback, not Muse. */
  isFallback?: boolean;
  /** Evidence for the sharedMeaning Muse call, when one ran. */
  museEvidence?: MuseCallEvidence | null;
  /** Layout positions in 0..1. */
  anchors: { index: number; x: number; y: number }[];
}

export interface DailyConstellationsView {
  day: CycleDay;
  colorId: DayColorId;
  /** Distinct players who answered today. The only number shown to players. */
  answeredToday: number;
  placement: "pending" | "ready" | "final";
  myStarIndex: number;
  constellations: DailyConstellation[];
}

// ---- S6 your week -------------------------------------------------------------
export interface WeekDay {
  day: CycleDay;
  colorId: DayColorId;
  released: boolean;
  answered: boolean;
  isCatchUp: boolean;
  /** The viewer's own constellations that day. */
  constellationCount: number;
}
export interface WeekView {
  cycleId: string;
  days: WeekDay[];
}

// ---- S15 custom-event approval -------------------------------------------------
export interface CustomEventProposal {
  proposalId: string;
  clusterSize: number;
  title: string;
  why: string;
  placeId: string;
  timeWindow: { startsAt: string; endsAt: string };
  evidence: MuseCallEvidence;
  status: "pending" | "approved" | "rejected";
}
export type ProposalDecision = "approve" | "reject";


// ---- S9 sky, S10 progress, S11 main (contract 3.0.0; mirrors protocol.ts exactly) ----
export interface SkyStarsView {
  weekSeed: string;
  count: number;
  /** base64 Int16Array [x0,y0,x1,y1,...] on a 0..32767 grid. */
  positions: string;
}
export interface MySkyView {
  myStarIndex: number;
  mine: { constellationId: string; day: CycleDay; colorId: DayColorId; starIndices: number[] }[];
  secondDegree: { constellationId: string; viaStarIndex: number; starIndices: number[] }[];
}
export interface FormationAttempt {
  seq: number;
  fromStarIndex: number;
  toStarIndex: number;
  outcome: "tried" | "kept" | "dropped";
}
export interface ProgressEvent {
  phase: "queued" | "running" | "done";
  step: number;
  totalSteps: number;
  attempts: FormationAttempt[];
  source: "trace" | "visualization";
  isVisualization: boolean;
}
export type MainReason = "no_match" | "opted_out" | "no_answers";
export interface MainConstellationView {
  constellationId: string;
  roomId: string;
  /** R1: room-local. Never equals the sky star index. */
  myRoomIndex: number;
  roomIndices: number[];
  anchors: { index: number; t: number }[];
  brightness: Record<number, Brightness>;
  revealedAt: string;
  roomExpiresAt: string;
}
export interface MainConstellationResponse {
  main: MainConstellationView | null;
  reason: MainReason | null;
}

/** v3 calls. Optional on CycleClient until contract 3.0.0 and the producer routes land. */
export interface V3Client {
  dailyConstellations(cycleId: string, day: CycleDay, signal?: AbortSignal): Promise<DailyConstellationsView>;
  week(cycleId: string, signal?: AbortSignal): Promise<WeekView>;
  /** Operator: run day-close formation for a released day ("Demo timing"). */
  closeDay(cycleId: string, day: CycleDay): Promise<{ jobId: string }>;
  skyStars(cycleId: string, signal?: AbortSignal): Promise<SkyStarsView>;
  skyMine(cycleId: string, signal?: AbortSignal): Promise<MySkyView>;
  formationProgress(cycleId: string, signal?: AbortSignal): Promise<ProgressEvent>;
  main(cycleId: string, signal?: AbortSignal): Promise<MainConstellationResponse>;
  customEvents(signal?: AbortSignal): Promise<CustomEventProposal[]>;
  decideCustomEvent(proposalId: string, decision: ProposalDecision, note?: string): Promise<CustomEventProposal>;
}

// ---- runtime validators -------------------------------------------------------
type Rec = Record<string, unknown>;
const bad = (): never => {
  // Never echo the payload.
  throw new ClientError("PROVIDER_UNAVAILABLE", "The server sent an unexpected response.", true);
};
const rec = (v: unknown): Rec => (typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Rec) : bad());
const str = (v: unknown): string => (typeof v === "string" ? v : bad());
const bool = (v: unknown): boolean => (typeof v === "boolean" ? v : bad());
const int = (v: unknown, min: number, max: number): number =>
  typeof v === "number" && Number.isInteger(v) && v >= min && v <= max ? v : bad();
const unit = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) && v >= 0 && v <= 1 ? v : bad());
const oneOf = <T extends string>(v: unknown, options: readonly T[]): T => (options.includes(v as T) ? (v as T) : bad());
const list = <T>(v: unknown, parse: (x: unknown) => T, max = 1000): T[] =>
  Array.isArray(v) && v.length <= max ? v.map(parse) : bad();
const day = (v: unknown): CycleDay => int(v, 1, 5) as CycleDay;
const isoTime = (v: unknown): string =>
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(str(v)) ? (v as string) : bad();
const STAR_MAX = 1_000_000;

const MUSE_CALL_TYPES = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10"] as const;
function parseDropEvidence(v: unknown): MuseCallEvidence | null {
  if (v === undefined || v === null) return null;
  const o = rec(v);
  return {
    model: str(o.model).slice(0, 80),
    source: oneOf(o.source, ["live", "replay"] as const),
    generatedAt: isoTime(o.generatedAt),
    latencyMs: int(o.latencyMs, 0, 3_600_000),
    callType: oneOf(o.callType, MUSE_CALL_TYPES),
  };
}

export function parseDailyConstellations(v: unknown): DailyConstellationsView {
  const o = rec(v);
  const myStarIndex = int(o.myStarIndex, 0, STAR_MAX);
  const constellations = list(
    o.constellations,
    (x) => {
      const c = rec(x);
      const starIndices = list(c.starIndices, (i) => int(i, 0, STAR_MAX), 12);
      if (starIndices.length < 3 || !starIndices.includes(myStarIndex)) bad();
      return {
        constellationId: str(c.constellationId),
        starIndices,
        brightness: oneOf(c.brightness, ["bright", "mid", "faint"] as const),
        sharedMeaning: typeof c.sharedMeaning === "string" && c.sharedMeaning.trim() ? c.sharedMeaning.trim().slice(0, 240) : null,
        memberCount: c.memberCount === undefined ? starIndices.length : int(c.memberCount, 1, 1000),
        isFallback: c.isFallback === undefined ? false : bool(c.isFallback),
        museEvidence: parseDropEvidence(c.museEvidence),
        anchors: list(
          c.anchors,
          (a) => {
            const p = rec(a);
            return { index: int(p.index, 0, STAR_MAX), x: unit(p.x), y: unit(p.y) };
          },
          12,
        ),
      };
    },
    3,
  );
  const parsedDay = day(o.day);
  return {
    day: parsedDay,
    colorId: oneOf(o.colorId, COLOR_IDS),
    answeredToday: int(o.answeredToday, 0, 10_000_000),
    placement: oneOf(o.placement, ["pending", "ready", "final"] as const),
    myStarIndex,
    constellations,
  };
}

export function parseSkyStars(v: unknown): SkyStarsView {
  const o = rec(v);
  const count = int(o.count, 0, 20_000);
  const positions = str(o.positions);
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(positions) || positions.length > 100_000) bad();
  return { weekSeed: str(o.weekSeed), count, positions };
}

export function parseMySky(v: unknown): MySkyView {
  const o = rec(v);
  const stars = (x: unknown) => list(x, (i) => int(i, 0, STAR_MAX), 3000);
  return {
    myStarIndex: int(o.myStarIndex, 0, STAR_MAX),
    mine: list(o.mine, (x) => {
      const c = rec(x);
      return { constellationId: str(c.constellationId), day: day(c.day), colorId: oneOf(c.colorId, COLOR_IDS), starIndices: stars(c.starIndices) };
    }, 15),
    secondDegree: list(o.secondDegree, (x) => {
      const c = rec(x);
      return { constellationId: str(c.constellationId), viaStarIndex: int(c.viaStarIndex, 0, STAR_MAX), starIndices: stars(c.starIndices) };
    }, 40),
  };
}

export function parseProgress(v: unknown): ProgressEvent {
  const o = rec(v);
  const source = oneOf(o.source, ["trace", "visualization"] as const);
  const isVisualization = bool(o.isVisualization);
  if (isVisualization !== (source === "visualization")) bad(); // contract: always equal
  return {
    phase: oneOf(o.phase, ["queued", "running", "done"] as const),
    step: int(o.step, 0, 100_000),
    totalSteps: int(o.totalSteps, 0, 100_000),
    attempts: list(o.attempts, (x) => {
      const a = rec(x);
      return {
        seq: int(a.seq, 0, 1_000_000),
        fromStarIndex: int(a.fromStarIndex, 0, STAR_MAX),
        toStarIndex: int(a.toStarIndex, 0, STAR_MAX),
        outcome: oneOf(a.outcome, ["tried", "kept", "dropped"] as const),
      };
    }, 200),
    source,
    isVisualization,
  };
}

export function parseMain(v: unknown): MainConstellationResponse {
  const o = rec(v);
  const reason = o.reason === null ? null : oneOf(o.reason, ["no_match", "opted_out", "no_answers"] as const);
  if (o.main === null) {
    if (reason === null) bad();
    return { main: null, reason };
  }
  if (reason !== null) bad();
  const m = rec(o.main);
  const roomIndices = list(m.roomIndices, (i) => int(i, 0, 99), 5);
  const myRoomIndex = int(m.myRoomIndex, 0, 99);
  if (roomIndices.length < 3 || !roomIndices.includes(myRoomIndex)) bad();
  const brightnessRaw = rec(m.brightness);
  const brightness: Record<number, Brightness> = {};
  for (const [k, val] of Object.entries(brightnessRaw)) {
    const idx = Number(k);
    if (!roomIndices.includes(idx)) bad();
    brightness[idx] = oneOf(val, ["bright", "mid", "faint"] as const);
  }
  return {
    main: {
      constellationId: str(m.constellationId),
      roomId: str(m.roomId),
      myRoomIndex,
      roomIndices,
      anchors: list(m.anchors, (x) => {
        const a = rec(x);
        return { index: int(a.index, 0, 99), t: unit(a.t) };
      }, 5),
      brightness,
      revealedAt: isoTime(m.revealedAt),
      roomExpiresAt: isoTime(m.roomExpiresAt),
    },
    reason: null,
  };
}

export function parseWeekView(v: unknown): WeekView {
  const o = rec(v);
  const days = list(
    o.days,
    (x) => {
      const d = rec(x);
      return {
        day: day(d.day),
        colorId: oneOf(d.colorId, COLOR_IDS),
        released: bool(d.released),
        answered: bool(d.answered),
        isCatchUp: bool(d.isCatchUp),
        constellationCount: int(d.constellationCount, 0, 3),
      };
    },
    5,
  );
  return { cycleId: str(o.cycleId), days };
}

export function parseProposal(v: unknown, parseEvidence: (x: unknown) => MuseCallEvidence): CustomEventProposal {
  const o = rec(v);
  const w = rec(o.timeWindow);
  return {
    proposalId: str(o.proposalId),
    clusterSize: int(o.clusterSize, 0, 10_000),
    title: str(o.title),
    why: str(o.why),
    placeId: str(o.placeId),
    timeWindow: { startsAt: isoTime(w.startsAt), endsAt: isoTime(w.endsAt) },
    evidence: parseEvidence(o.evidence),
    status: oneOf(o.status, ["pending", "approved", "rejected"] as const),
  };
}
