/*
 * Daily-loop client boundary (owner: Will).
 * Wire types come from contracts/protocol.ts (type-only import, erased at build).
 * TypeScript types are not validation: every server response is checked by the
 * hand validators below before the UI uses it.
 */
import type {
  ApiError,
  CatchUpState,
  CycleDay,
  DailyAnswer,
  DailyQuestion,
  ErrorCode,
  M2Out,
  MuseCallEvidence,
  Report,
  Streak,
  WeeklyCycle,
} from "../../../../../contracts/protocol";

export type {
  CatchUpState,
  CycleDay,
  DailyAnswer,
  DailyQuestion,
  ErrorCode,
  MuseCallEvidence,
  Report,
  Streak,
  WeeklyCycle,
};

import { parseFormationDebug, type FormationDebugProps } from "../formation";
import type { NudgeRequester } from "../nudges";
import type { V3Client } from "./v3";
import type { ReasoningEntry } from "../operator/reasoning";

export type { FormationDebugProps };

/** Accepts Rishi's debug object alone or wrapped as {data, evidence, totalMs, usedFallback}. */
export function parseFormationResponse(v: unknown): FormationDebugProps | null {
  if (typeof v !== "object" || v === null) return null;
  const o = v as Record<string, unknown>;
  const data = parseFormationDebug(o.data ?? o);
  if (!data) return null;
  const evidence = Array.isArray(o.evidence)
    ? o.evidence.flatMap((item) => {
        try {
          const e = parseEvidence(item);
          return e.callType === "M3" || e.callType === "M4" || e.callType === "M5" || e.callType === "M8"
            ? [{ callType: e.callType, model: e.model, source: e.source, latencyMs: e.latencyMs }]
            : [];
        } catch {
          return [];
        }
      })
    : [];
  return {
    data,
    evidence,
    totalMs: typeof o.totalMs === "number" && Number.isFinite(o.totalMs) ? o.totalMs : 0,
    usedFallback: o.usedFallback === true,
  };
}

export interface CurrentCycle {
  cycle: WeeklyCycle;
  question: DailyQuestion | null;
  streak: Streak;
  catchUp: CatchUpState;
}
export interface AnswerResult {
  answer: DailyAnswer;
  supportCard: boolean;
}
/** M2 result. `evidence` is optional until the follow-up route returns it. */
export interface FollowUp extends M2Out {
  evidence?: MuseCallEvidence;
}
export interface Transcript {
  transcript: string;
  mode: "live" | "fixture";
}
export interface TopUpResult {
  label: string;
  syntheticPlayers: number;
  answersAdded: number;
}

export class ClientError extends Error {
  code: ErrorCode;
  retryable: boolean;
  constructor(code: ErrorCode, message: string, retryable = false) {
    super(message);
    this.code = code;
    this.retryable = retryable;
  }
}

export interface CycleClient {
  /** "fixture" = in-browser test adapter: no server, no Muse. Shown in the UI. */
  readonly mode: "live" | "fixture";
  readonly isOperator: boolean;
  /** Resolves null when no cycle exists yet. */
  current(signal?: AbortSignal): Promise<CurrentCycle | null>;
  questions(cycleId: string, signal?: AbortSignal): Promise<DailyQuestion[]>;
  myAnswers(cycleId: string, signal?: AbortSignal): Promise<DailyAnswer[]>;
  submit(
    cycleId: string,
    body: { day: CycleDay; text: string; source: "voice" | "text" },
  ): Promise<AnswerResult>;
  edit(
    cycleId: string,
    day: CycleDay,
    body: { text: string; answersFollowUp?: boolean },
  ): Promise<AnswerResult>;
  remove(cycleId: string, day: CycleDay): Promise<void>;
  followUp(cycleId: string, day: CycleDay, signal?: AbortSignal): Promise<FollowUp>;
  transcribe(audio: Blob, signal?: AbortSignal): Promise<Transcript>;
  /** PROPOSED (D013): WebSocket URL for live speech-to-text, or null when this
   *  client has none (fixture mode). The server may still lack the route; the
   *  UI then falls back to ``transcribe``. */
  liveTranscriptionUrl?(): string | null;
  // Operator controls ("Demo timing").
  createCycle(): Promise<WeeklyCycle>;
  advance(cycleId: string): Promise<WeeklyCycle>;
  topUp(cycleId: string): Promise<TopUpResult>;
  reset(cycleId: string): Promise<WeeklyCycle>;
  calls(signal?: AbortSignal): Promise<MuseCallEvidence[]>;
  reports(signal?: AbortSignal): Promise<Report[]>;
  /** Rishi's operator-only formation comparison (ids only). Null when there is none. */
  formationDebug(cycleId: string, signal?: AbortSignal): Promise<FormationDebugProps | null>;
  /**
   * The signed-in player's own constellation room for a cycle (Kai's
   * `GET /cycles/:id/room`), or null before reveal / when they have none.
   * The operator console uses it as the room to nudge in the demo.
   */
  myRoomId(cycleId: string, signal?: AbortSignal): Promise<string | null>;
  /** Adam's M7 nudge call: live `POST /operator/rooms/:id/nudge`; fixture returns a labeled replay. */
  readonly nudge: NudgeRequester;
  /**
   * v3 calls (PENDING contract 3.0.0, D012): daily reveal, week view, close day,
   * custom-event approval. Absent when this client has none.
   */
  readonly v3?: V3Client;
  /** Adam's GET /operator/reasoning (PROPOSED): Muse calls and the code verdicts on them. */
  reasoning?(signal?: AbortSignal): Promise<ReasoningEntry[]>;
  /** Fixture only: forget this tab's answers after "delete my data". */
  clearLocalData?(): void;
  /** Fires when cycle state may have changed (operator action, SSE later). */
  subscribe(listener: () => void): () => void;
}

// ---- runtime validators ------------------------------------------------------
type Rec = Record<string, unknown>;
const bad = (): never => {
  // Never include the payload: it may hold private answer text.
  throw new ClientError("PROVIDER_UNAVAILABLE", "The server sent an unexpected response.", true);
};
const rec = (v: unknown): Rec =>
  typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Rec) : bad();
const str = (v: unknown): string => (typeof v === "string" ? v : bad());
const bool = (v: unknown): boolean => (typeof v === "boolean" ? v : bad());
const num = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) ? v : bad());
const int = (v: unknown, min: number, max: number): number => {
  const n = num(v);
  return Number.isInteger(n) && n >= min && n <= max ? n : bad();
};
const oneOf = <T extends string>(v: unknown, options: readonly T[]): T =>
  options.includes(v as T) ? (v as T) : bad();
const nullable = <T>(v: unknown, parse: (x: unknown) => T): T | null =>
  v === null ? null : parse(v);
const list = <T>(v: unknown, parse: (x: unknown) => T): T[] =>
  Array.isArray(v) ? v.map(parse) : bad();
const isoTime = (v: unknown): string =>
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(str(v)) ? (v as string) : bad();
const isoDate = (v: unknown): string => (/^\d{4}-\d{2}-\d{2}$/.test(str(v)) ? (v as string) : bad());
const day = (v: unknown): CycleDay => int(v, 1, 5) as CycleDay;

const STATUSES = ["open", "locked", "forming", "revealed", "closed"] as const;

export function parseCycle(v: unknown): WeeklyCycle {
  const o = rec(v);
  return {
    cycleId: str(o.cycleId),
    communityId: str(o.communityId),
    weekStart: isoDate(o.weekStart),
    status: oneOf(o.status, STATUSES),
    currentDay: day(o.currentDay),
    locksAt: isoTime(o.locksAt),
    revealsAt: isoTime(o.revealsAt),
    chatExpiresAt: isoTime(o.chatExpiresAt),
    demoTiming: bool(o.demoTiming),
  };
}

export function parseDailyQuestion(v: unknown): DailyQuestion {
  const o = rec(v);
  const q = rec(o.question);
  return {
    cycleId: str(o.cycleId),
    day: day(o.day),
    date: isoDate(o.date),
    question: {
      questionId: str(q.questionId),
      text: str(q.text),
      category: oneOf(q.category, [
        "routine",
        "belonging",
        "interests",
        "values",
        "hopes",
        "small_joys",
        "challenges",
      ] as const),
      sensitivity: oneOf(q.sensitivity, ["low", "medium"] as const),
      signalTags: list(q.signalTags, str),
      followUpHint: nullable(q.followUpHint, str),
      source: oneOf(q.source, ["curated", "generated"] as const),
      active: bool(q.active),
    },
  };
}

export function parseAnswer(v: unknown): DailyAnswer {
  const o = rec(v);
  const text = str(o.text);
  if (text.length < 1 || text.length > 400) bad();
  return {
    answerId: str(o.answerId),
    cycleId: str(o.cycleId),
    day: day(o.day),
    questionId: str(o.questionId),
    playerId: str(o.playerId),
    text,
    source: oneOf(o.source, ["voice", "text"] as const),
    isCatchUp: bool(o.isCatchUp),
    weight: num(o.weight),
    followUpUsed: bool(o.followUpUsed),
    createdAt: isoTime(o.createdAt),
    editedAt: nullable(o.editedAt, isoTime),
    deletedAt: nullable(o.deletedAt, isoTime),
  };
}

export function parseStreak(v: unknown): Streak {
  const o = rec(v);
  return {
    playerId: str(o.playerId),
    communityId: str(o.communityId),
    current: int(o.current, 0, 100000),
    longest: int(o.longest, 0, 100000),
    lastOnDayDate: nullable(o.lastOnDayDate, isoDate),
  };
}

export function parseCurrent(v: unknown): CurrentCycle {
  const o = rec(v);
  const c = rec(o.catchUp);
  return {
    cycle: parseCycle(o.cycle),
    question: nullable(o.question, parseDailyQuestion),
    streak: parseStreak(o.streak),
    catchUp: { cycleId: str(c.cycleId), missedDays: list(c.missedDays, day), closesAt: isoTime(c.closesAt) },
  };
}

export function parseAnswerResult(v: unknown): AnswerResult {
  const o = rec(v);
  return { answer: parseAnswer(o.answer), supportCard: bool(o.supportCard) };
}

export function parseEvidence(v: unknown): MuseCallEvidence {
  const o = rec(v);
  return {
    model: str(o.model).slice(0, 60),
    source: oneOf(o.source, ["live", "replay"] as const),
    generatedAt: isoTime(o.generatedAt),
    latencyMs: num(o.latencyMs),
    callType: oneOf(o.callType, ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"] as const),
  };
}

export function parseFollowUp(v: unknown): FollowUp {
  const o = rec(v);
  const question = str(o.question);
  if (question.length > 200) bad();
  return {
    needsFollowup: bool(o.needsFollowup),
    question,
    ...(o.evidence === undefined ? {} : { evidence: parseEvidence(o.evidence) }),
  };
}

export function parseTranscript(v: unknown): Transcript {
  const o = rec(v);
  return { transcript: str(o.transcript).slice(0, 400), mode: oneOf(o.mode, ["live", "fixture"] as const) };
}

export function parseTopUp(v: unknown): TopUpResult {
  const o = rec(v);
  return {
    label: str(o.label),
    syntheticPlayers: int(o.syntheticPlayers, 0, 10000),
    answersAdded: int(o.answersAdded, 0, 100000),
  };
}

export function parseReport(v: unknown): Report {
  const o = rec(v);
  return {
    reportId: str(o.reportId),
    roomId: str(o.roomId),
    messageId: nullable(o.messageId, str),
    reporterId: str(o.reporterId),
    reportedHandle: str(o.reportedHandle),
    reason: oneOf(o.reason, ["harassment", "self_harm", "spam", "personal_info", "other"] as const),
    createdAt: isoTime(o.createdAt),
  };
}

const CODES: readonly ErrorCode[] = [
  "INVALID_INPUT",
  "UNAUTHENTICATED",
  "FORBIDDEN",
  "NOT_FOUND",
  "CONSENT_REQUIRED",
  "STALE_REVISION",
  "PROVIDER_UNAVAILABLE",
  "RATE_LIMITED",
  "IDEMPOTENCY_CONFLICT",
  "CYCLE_LOCKED",
  "ROOM_EXPIRED",
  "MESSAGE_REJECTED",
];

export function parseApiError(v: unknown): ApiError["error"] {
  const e = rec(rec(v).error);
  return {
    code: oneOf(e.code, CODES),
    message: str(e.message).slice(0, 200),
    requestId: str(e.requestId),
    retryable: bool(e.retryable),
  };
}

export { list as parseList };
