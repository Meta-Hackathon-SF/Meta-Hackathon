/**
 * Constellations wire contract v2.0.0 (weekly game). Supersedes 1.0.0 (hunt rounds).
 * Pending D006 ACK from all five owners (see docs/DECISIONS.md).
 * Definitions only: every consumer MUST implement runtime validation
 * (Pydantic on the server, zod or hand validators in the browser).
 * JSON keys are camelCase across TypeScript and Python, including Muse job I/O.
 * PRIVATE = server-side only, never returned to another player.
 * PUBLIC  = safe in responses to authorized session holders as annotated.
 * Fixtures that conform to this file: contracts/fixtures/*.json.
 */
export const CONTRACT_VERSION = "2.0.0" as const;
export type Id = string;
export type IsoTime = string; // RFC3339 UTC
export type IsoDate = string; // YYYY-MM-DD in the community time zone
export type TimeWindow = { start: IsoTime; end: IsoTime };

// ---- Players, consent, sessions (Patrik) --------------------------------
export interface Player { // PUBLIC only after mutual reveal; otherwise use AnonymousHandle
  playerId: Id; displayName: string; avatarColor: string; isSynthetic: boolean;
}
export interface Consent { // PRIVATE (self + privacy module)
  playerId: Id; communityId: Id;
  matchAnswers: boolean;  // use my answers to form my weekly constellation
  anonymousChat: boolean; // join my constellation's anonymous chat on Sunday
  isAdult: boolean;       // 18+
  version: number; revokedAt: IsoTime | null;
}
export interface Block { blockerId: Id; blockedId: Id } // PRIVATE; never share a constellation
export type SafetyLevel = "none" | "distress" | "harm";
export interface SafetyFlag { // PRIVATE
  subjectType: "answer" | "chat_message"; subjectId: Id; flag: SafetyLevel; reason: string;
}

// ---- Question bank (Adam) -----------------------------------------------
export type QuestionCategory =
  | "routine" | "belonging" | "interests" | "values" | "hopes" | "small_joys" | "challenges";
export type Sensitivity = "low" | "medium"; // "high" questions are never stored in the bank
export interface Question { // PUBLIC text; metadata server-side
  questionId: Id; text: string; // 10-140 chars, open-ended, no yes/no
  category: QuestionCategory; sensitivity: Sensitivity;
  signalTags: string[]; // semantic dimensions the answer informs, e.g. ["solitude","meals"]
  followUpHint: string | null; // optional nudge Muse may use for M2
  source: "curated" | "generated"; // generated = M6 output that passed guards
  active: boolean;
}

// ---- Weekly cycle, daily answers, streaks (Will) ------------------------
/** Mon-Fri: one daily question per day. Sat 12:00 local: lock. Sun 10:00 local: reveal. */
export type CycleStatus = "open" | "locked" | "forming" | "revealed" | "closed";
export type CycleDay = 1 | 2 | 3 | 4 | 5; // Mon..Fri question days
export interface WeeklyCycle { // PUBLIC
  cycleId: Id; communityId: Id; weekStart: IsoDate; // Monday
  status: CycleStatus;
  currentDay: CycleDay;
  locksAt: IsoTime; revealsAt: IsoTime; chatExpiresAt: IsoTime; // next cycle's lock
  demoTiming: boolean; // true -> operator advances days; UI shows "Demo timing"
}
export interface DailyQuestion { // PUBLIC
  cycleId: Id; day: CycleDay; date: IsoDate; question: Question;
}
export interface DailyAnswer { // PRIVATE: author + server only
  answerId: Id; cycleId: Id; day: CycleDay; questionId: Id; playerId: Id;
  text: string; // 1-400 chars
  source: "voice" | "text";
  isCatchUp: boolean; // answered after its day, before Saturday lock
  weight: number;     // server-set: see WEIGHTS; never client-supplied
  followUpUsed: boolean;
  createdAt: IsoTime; editedAt: IsoTime | null; deletedAt: IsoTime | null;
}
export const WEIGHTS = { onDay: 1.0, catchUp: 0.6, followUpBonus: 0.1, max: 1.1 } as const;
export interface Streak { // PRIVATE to self
  playerId: Id; communityId: Id;
  current: number; longest: number; // consecutive question days answered ON the day
  lastOnDayDate: IsoDate | null; // catch-up answers never extend a streak
}
export interface CatchUpState { // PRIVATE to self
  cycleId: Id; missedDays: CycleDay[]; closesAt: IsoTime; // = locksAt
}
export interface PrevalenceGuess { // PRIVATE, stored apart from answers
  cycleId: Id; playerId: Id; percent: number; // 0-100: "how many here feel like you this week?"
}

// ---- Formation and Sky (Rishi produces, Kai renders) --------------------
export interface Theme { // PRIVATE
  themeId: Id; cycleId: Id; label: string; description: string;
  memberIds: Id[]; weightedSupport: number;
}
export interface Constellation {
  constellationId: Id; cycleId: Id;
  memberIds: Id[];       // PRIVATE: members see AnonymousHandles, never ids, until mutual reveal
  sharedMeaning: string; // PRIVATE (may paraphrase answers)
  confidence: number;    // 0-1
  isLooseMatch: boolean; // UI copy: "Your connection here is looser this week"
  name: string;          // PUBLIC to members; passes OutputGuard
  shapeId: string; colorId: string; // fixed sets, sized to member count
  baselineAgrees: boolean; // keyword baseline grouped these members the same way
}
export interface SkyTheme { // PUBLIC aggregate; rendered only if count >= threshold
  themeId: Id; label: string; count: number;
  actualPercent: number;       // count / eligible players
  guessedPercentMedian: number; // from PrevalenceGuess of members of this theme
}
export interface SkyStats { // PUBLIC; Rishi computes, Kai serves + renders
  cycleId: Id; threshold: number; // 3 demo, 25 production
  eligiblePlayers: number; constellations: number; mutualReveals: number;
  themes: SkyTheme[]; // already filtered by threshold
  suppressedThemes: number; // count only, no labels
  headlines: string[]; // M8, numbers checked against server counts
  syntheticSignals: SyntheticSignal[]; // labeled, never merged into counts
  evidence: MuseCallEvidence[];
}
/** Aggregate-only signal from a synthetic population. UI label: "Synthetic signal". */
export interface SyntheticSignal { // PUBLIC
  signalId: Id; label: string; percent: number; sampleSize: number; source: "synthetic";
}

// ---- Anonymous chat, moderation, reveal (Kai; moderation calls Patrik) --
export interface AnonymousHandle { // PUBLIC to room members
  roomId: Id; handle: string; // e.g. "Star 3"; never derived from name
  starColor: string; isSelf: boolean;
}
export type RoomStatus = "open" | "expired" | "closed";
export interface ChatRoom { // PUBLIC to members
  roomId: Id; constellationId: Id; cycleId: Id;
  status: RoomStatus; opensAt: IsoTime; expiresAt: IsoTime;
  members: AnonymousHandle[];
}
export type ModerationState = "visible" | "hidden_pending" | "removed";
export interface ChatMessage { // PUBLIC to room members
  messageId: Id; roomId: Id; handle: string; text: string; // 1-500 chars
  createdAt: IsoTime; moderation: ModerationState;
  kind: "player" | "muse_nudge" | "system";
}
export interface Report { // PRIVATE
  reportId: Id; roomId: Id; messageId: Id | null; reporterId: Id; reportedHandle: string;
  reason: "harassment" | "self_harm" | "spam" | "personal_info" | "other"; createdAt: IsoTime;
}
export interface RevealRequest { // PRIVATE; requester sees own pending list only
  roomId: Id; fromPlayerId: Id; toHandle: string; createdAt: IsoTime;
}
export type RevealResult = "pending" | "revealed"; // never tells the requester the other said no
export interface MutualReveal { // PUBLIC to the two players only
  roomId: Id; players: [Player, Player]; revealedAt: IsoTime;
}

// ---- Event nudges (Adam) ------------------------------------------------
export interface Venue { placeId: Id; name: string; kind: "cafe" | "dining_hall" | "library" | "park" | "rec_center" | "campus_event"; isPublic: true }
export interface EventNudge { // PUBLIC to room members, posted as a muse_nudge message
  nudgeId: Id; constellationId: Id; title: string; placeId: Id;
  timeWindow: TimeWindow; why: string; // passes OutputGuard; never quotes answers
  minAttendees: 3; evidence: MuseCallEvidence;
}

// ---- Realtime (Kai) -----------------------------------------------------
export type StreamEvent =
  | { type: "cycle.updated"; seq: number; cycle: WeeklyCycle }
  | { type: "constellation.revealed"; seq: number; roomId: Id }
  | { type: "chat.message"; seq: number; message: ChatMessage }
  | { type: "chat.moderated"; seq: number; messageId: Id; moderation: ModerationState }
  | { type: "reveal.mutual"; seq: number; reveal: MutualReveal }
  | { type: "room.expired"; seq: number; roomId: Id }
  | { type: "sky.updated"; seq: number; cycleId: Id };

// ---- Evidence and errors ------------------------------------------------
export interface ModelEvidence {
  model: string; source: "live" | "replay"; generatedAt: IsoTime; latencyMs: number;
}
export type MuseCallType = "M1" | "M2" | "M3" | "M4" | "M5" | "M6" | "M7" | "M8";
export interface MuseCallEvidence extends ModelEvidence { callType: MuseCallType }
export type ErrorCode =
  | "INVALID_INPUT" | "UNAUTHENTICATED" | "FORBIDDEN" | "NOT_FOUND"
  | "CONSENT_REQUIRED" | "STALE_REVISION" | "PROVIDER_UNAVAILABLE" | "RATE_LIMITED"
  | "IDEMPOTENCY_CONFLICT" | "CYCLE_LOCKED" | "ROOM_EXPIRED" | "MESSAGE_REJECTED";
export interface ApiError {
  error: { code: ErrorCode; message: string; requestId: Id; retryable: boolean };
}

// ---- Muse jobs ----------------------------------------------------------
// Inputs carry random per-call ids and text only. No names, emails, photos or
// session tokens. Outputs are schema-validated, then code-checked (OutputGuard).
export type MuseTask =
  | "safety_screen" | "clarify" | "theme_discovery" | "constellation_formation"
  | "constellation_naming" | "question_generation" | "event_nudge" | "sky_narration";
export interface PromptText { id: string; text: string; weight?: number } // id random per call

export interface M1In { text: PromptText; subjectType: "answer" | "chat_message" } // Patrik
export interface M1Out { flag: SafetyLevel; reason: string }
export interface M2In { question: string; answer: PromptText } // Adam, called by Will
export interface M2Out { needsFollowup: boolean; question: string }
export interface M3In { answers: PromptText[]; questions: { questionId: string; text: string }[] } // Rishi
export interface M3Out { themes: { id: string; label: string; description: string; memberIds: string[] }[] }
export interface M4In { themes: M3Out["themes"]; answers: PromptText[]; blockedPairs: [string, string][] } // Rishi
export interface M4Out { constellations: { memberIds: string[]; sharedMeaning: string; confidence: number }[] }
export interface M5In { sharedMeaning: string; size: number } // Rishi
export interface M5Out { name: string; shapeId: string; colorId: string }
export interface M6In { // Adam
  recentQuestionIds: string[]; categoryMix: Record<QuestionCategory, number>;
  aggregateSignals: { tag: string; share: number }[]; // aggregate only, never answers
  count: number;
}
export interface M6Out { questions: Omit<Question, "questionId" | "source" | "active">[] }
export interface M7In { // Adam
  sharedMeaning: string; venues: Venue[]; window: TimeWindow; campusEvents: { title: string; placeId: string; start: IsoTime }[];
}
export interface M7Out { title: string; placeId: string; timeWindow: TimeWindow; why: string }
export interface M8In { // Rishi; counts only
  eligiblePlayers: number; constellations: number;
  themes: { label: string; count: number; actualPercent: number; guessedPercentMedian: number }[];
}
export interface M8Out { headlines: string[] } // every number must equal an input number

export interface MuseJobMap {
  safety_screen: { in: M1In; out: M1Out };
  clarify: { in: M2In; out: M2Out };
  theme_discovery: { in: M3In; out: M3Out };
  constellation_formation: { in: M4In; out: M4Out };
  constellation_naming: { in: M5In; out: M5Out };
  question_generation: { in: M6In; out: M6Out };
  event_nudge: { in: M7In; out: M7Out };
  sky_narration: { in: M8In; out: M8Out };
}

// ---- Ports between owners (server-side; Python mirrors these) -----------
/** Adam: the only Muse adapter. Strict JSON, one retry, then labeled fallback or error. */
export interface MusePort {
  run<T extends MuseTask>(input: {
    task: T; requestId: Id; promptVersion: string; payload: MuseJobMap[T]["in"]; signal?: AbortSignal;
  }): Promise<{ output: MuseJobMap[T]["out"]; evidence: MuseCallEvidence }>;
}
/** Patrik: sessions, authorized snapshots, safety, guards. */
export interface PrivacyPort {
  requireSession(token: string): Promise<{ playerId: Id; communityId: Id; isOperator: boolean }>;
  formationSnapshot(cycleId: Id): Promise<{ answers: PromptText[]; idMap: Record<string, Id>; blockedPairs: [Id, Id][] }>;
  screen(text: string, subjectType: "answer" | "chat_message"): Promise<SafetyFlag["flag"]>;
}
export interface OutputGuard { // Patrik; applied to every Muse text and every chat message
  check(text: string, againstAnswers: string[]): {
    ok: boolean; reasons: ("quote_5_words" | "sensitive_term" | "pii" | "contact_info")[];
  };
}
/** Rishi: semantic formation + validation + prevalence. */
export interface FormationPort {
  form(cycleId: Id): Promise<
    | { status: "ok"; constellations: Constellation[]; evidence: MuseCallEvidence[] }
    | { status: "failed"; error: ApiError["error"] }
  >;
  computeSky(cycleId: Id, threshold: number): Promise<SkyStats>;
}
/** Adam: question bank + selection + event nudges. */
export interface QuestionPort {
  selectWeek(cycleId: Id, communityId: Id): Promise<DailyQuestion[]>; // 5 questions, Mon-Fri
}
export interface NudgePort { propose(constellationId: Id): Promise<EventNudge | null> }
/** Will: weekly cycle + answers + streaks. */
export interface CyclePort {
  current(communityId: Id): Promise<WeeklyCycle>;
  advance(cycleId: Id, to: CycleStatus | { day: CycleDay }): Promise<WeeklyCycle>; // operator only
}
/** Kai: chat rooms + reveal + realtime. */
export interface ChatPort {
  openRooms(cycleId: Id, constellations: Constellation[]): Promise<ChatRoom[]>;
  postSystem(roomId: Id, message: Omit<ChatMessage, "messageId" | "createdAt" | "moderation">): Promise<ChatMessage>;
  expire(cycleId: Id): Promise<number>;
}
