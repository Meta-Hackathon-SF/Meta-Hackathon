/**
 * Constellations wire contract v1.0.0. First Constellations contract;
 * pending D003 ACK from all five owners (see docs/DECISIONS.md).
 * Definitions only: consumers MUST implement runtime validation.
 * JSON keys are camelCase across TypeScript and Python, including Muse job I/O.
 * PRIVATE = server-side only, never returned to another player or the browser
 * of a non-author. PUBLIC = safe in responses to authorized session holders.
 */
export const CONTRACT_VERSION = "1.0.0" as const;
export type Id = string;
export type IsoTime = string; // RFC3339 UTC
export type Window = { start: IsoTime; end: IsoTime };

// ---- Players, consent, safety ------------------------------------------
export interface Player { // PUBLIC
  playerId: Id; displayName: string; avatarColor: string; isSynthetic: boolean;
}
export interface ConsentV2 { // PRIVATE (self + Patrik's privacy module)
  playerId: Id; roundId?: Id;
  matchAnswers: boolean; writeClues: boolean; isAdult: boolean; // 18+
  version: number; revokedAt: IsoTime | null;
}
export interface FindableDetails { // PRIVATE until used in a riddle
  playerId: Id; items: string[]; // self-approved: seat, hoodie colour, class
}
export interface Block { blockerId: Id; blockedId: Id } // PRIVATE
export type SafetyLevel = "none" | "distress" | "harm";
export interface SafetyFlag { // PRIVATE
  answerId: Id; flag: SafetyLevel; reason: string;
}

// ---- Round, answers, guesses -------------------------------------------
export type RoundStatus =
  | "open" | "locked" | "inducting" | "hunt" | "sky" | "closed";
export interface Round { // PUBLIC
  roundId: Id; communityId: Id; questionId: Id; questionText: string;
  status: RoundStatus; levelUnlocked: 0 | 1 | 2 | 3;
  demoTiming: boolean; // true -> UI shows "Demo timing"
}
export interface Answer { // PRIVATE: author + server only
  answerId: Id; roundId: Id; playerId: Id;
  text: string; // 1-400 chars
  source: "voice" | "text"; followUpUsed: boolean;
  createdAt: IsoTime; deletedAt: IsoTime | null;
}
export interface Guess { // PRIVATE, stored separately from Answer
  roundId: Id; playerId: Id; percent: number; // 0-100
}

// ---- Themes, societies, hunt -------------------------------------------
export interface Theme {
  themeId: Id; label: string; description: string;
  memberIds: Id[]; // PRIVATE; never leaves server
  size: number;
}
export interface Society {
  societyId: Id; roundId: Id;
  memberIds: Id[]; // PUBLIC only to members of this society
  sharedMeaning: string; // PRIVATE (may paraphrase answers)
  confidence: number; // 0-1
  isLooseMatch: boolean; // UI: "Your connection here is looser this week"
  name: string; motto: string; sigilId: string; colorId: string; // PUBLIC to members
}
export interface PassphraseHalf { // PRIVATE to the holder
  societyId: Id; playerId: Id; half: "a" | "b"; phrase: string;
}
export interface Riddle { // PUBLIC to seeker only, once released
  riddleId: Id; societyId: Id; seekerId: Id; targetId: Id; level: 1 | 2 | 3;
  text: string; releasedAt: IsoTime | null; vetoed: boolean; // P1 veto by target
}
export interface FoundCode { playerId: Id; code: string } // 4 chars, shown to holder
export interface Find { // mutual, idempotent, unique unordered pair
  societyId: Id; playerAId: Id; playerBId: Id; confirmedAt: IsoTime;
}
export type FindResult = "confirmed" | "pending" | "not_a_match";

// ---- Sky and ritual ----------------------------------------------------
export interface SkyTheme { // PUBLIC aggregate; only if count >= threshold
  label: string; guessedPercent: number; actualPercent: number; count: number;
}
export interface SkyStats { // PUBLIC
  roundId: Id; societies: number; finds: number; threshold: number; // 3 demo / 25 prod
  themes: SkyTheme[]; headlines: string[]; evidence: MuseCallEvidence;
}
export interface RitualQuest { // PUBLIC to society (P1)
  questId: Id; societyId: Id; title: string; placeId: Id;
  timeWindow: Window; why: string; budgetCapMinor: number;
  approvals: { playerId: Id; choice: "in" | "not_this_week" }[]; // created at >=3 "in"
}

// ---- Evidence and errors -----------------------------------------------
export interface ModelEvidence {
  model: string; source: "live" | "replay"; generatedAt: IsoTime; latencyMs: number;
}
export type MuseCallType = "M1" | "M2" | "M3" | "M4" | "M5" | "M6" | "M7" | "M8";
export interface MuseCallEvidence extends ModelEvidence { callType: MuseCallType }
export type ErrorCode =
  | "INVALID_INPUT" | "UNAUTHENTICATED" | "FORBIDDEN" | "NOT_FOUND"
  | "CONSENT_REQUIRED" | "STALE_REVISION" | "CAPACITY_REACHED"
  | "PROVIDER_UNAVAILABLE" | "RATE_LIMITED" | "IDEMPOTENCY_CONFLICT"
  | "ROUND_LOCKED" | "NOT_IN_SOCIETY"; // NOT_IN_SOCIETY is never sent for wrong codes
export interface ApiError {
  error: { code: ErrorCode; message: string; requestId: Id; retryable: boolean };
}

// ---- Muse jobs (camelCase like every wire key; PRD snake_case names map 1:1) ---------
// Inputs carry random per-call player IDs and answer text only. No names,
// emails, photos or session tokens. Outputs are schema-validated, then code-checked.
export type MuseTask =
  | "safety_screen" | "clarify" | "theme_discovery" | "society_formation"
  | "society_identity" | "riddles" | "ritual_quest" | "sky_narration";
export interface PromptAnswer { id: string; text: string } // id = random, per call

export interface M1In { answer: PromptAnswer }
export interface M1Out { flag: SafetyLevel; reason: string }
export interface M2In { answer: PromptAnswer }
export interface M2Out { needsFollowup: boolean; question: string }
export interface M3In { answers: PromptAnswer[] } // unflagged only
export interface M3Out {
  themes: { id: string; label: string; description: string; memberIds: string[] }[];
}
export interface M4In { themes: M3Out["themes"]; answers: PromptAnswer[] }
export interface M4Out {
  societies: { memberIds: string[]; sharedMeaning: string; confidence: number }[];
}
export interface M5In { sharedMeaning: string; answers: PromptAnswer[] }
export interface M5Out {
  name: string; motto: string; sigilId: string; colorId: string;
  phraseA: string; phraseB: string;
}
export interface M6In { targetAnswer: PromptAnswer; findableDetails: string[] } // per target per seeker
export interface M6Out {
  levels: [string, string, string]; // cryptic, medium, direct
  sensitiveSelfCheck: boolean; // true = Muse thinks it touched a sensitive category
}
export interface M7In {
  sharedMeaning: string; budgetCapMinor: number;
  venues: { placeId: string; name: string }[]; // approved public list
}
export interface M7Out {
  title: string; placeId: string; timeWindow: Window; why: string;
}
export interface M8In { // counts only, computed by the server; no answers
  societies: number; finds: number;
  themes: { label: string; guessedPercent: number; actualPercent: number; count: number }[];
}
export interface M8Out { headlines: string[] } // every number must equal server counts

export interface MuseJobMap {
  safety_screen: { in: M1In; out: M1Out };
  clarify: { in: M2In; out: M2Out };
  theme_discovery: { in: M3In; out: M3Out };
  society_formation: { in: M4In; out: M4Out };
  society_identity: { in: M5In; out: M5Out };
  riddles: { in: M6In; out: M6Out };
  ritual_quest: { in: M7In; out: M7Out };
  sky_narration: { in: M8In; out: M8Out };
}

// ---- Ports --------------------------------------------------------------
/** Adam: single Muse adapter (Keeper voice, strict JSON, one retry, labeled fallback). */
export interface KeeperPort {
  run<T extends MuseTask>(input: {
    task: T; requestId: Id; promptVersion: string;
    payload: MuseJobMap[T]["in"]; signal?: AbortSignal;
  }): Promise<{ output: MuseJobMap[T]["out"]; evidence: MuseCallEvidence }>;
}
/** Rishi: runs M3 then M4 for a locked round, validates, returns societies. */
export interface InductionPort {
  induct(roundId: Id): Promise<
    | { status: "ok"; societies: Society[]; evidence: MuseCallEvidence[] }
    | { status: "failed"; error: ApiError["error"] }
  >;
}
/** Patrik: applied to every Muse text output before release. */
export interface OutputGuard {
  check(text: string, answers: string[]): {
    ok: boolean;
    reasons: ("quote_5_words" | "sensitive_term" | "pii")[];
  };
}
