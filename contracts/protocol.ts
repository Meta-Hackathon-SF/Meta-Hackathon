/**
 * Facebook Space wire contract v3.0.0 (daily constellations, Saturday sky, Sunday main
 * constellation, 24 h chat, events). Breaking vs 2.2.0 (D012); builds on 2.2.0 (D014).
 * Pending ACK on the shapes each owner produces (issue #54, see docs/DECISIONS.md D012).
 * Sections marked "v3" are new. Types 3.0.0 retires are kept and marked @deprecated so the
 * 2.x server paths keep compiling; they are deleted in the follow-up PR once each owner migrates.
 * Definitions only: every consumer MUST implement runtime validation
 * (Pydantic on the server, zod or hand validators in the browser).
 * JSON keys are camelCase across TypeScript and Python, including Muse job I/O.
 * PRIVATE = server-side only, never returned to another player.
 * PUBLIC  = safe in responses to authorized session holders as annotated.
 * Fixtures that conform to this file: contracts/fixtures/*.json.
 */
export const CONTRACT_VERSION = "3.0.0" as const; // 2.1.0 = D009 + D010; 2.2.0 = D014; 3.0.0 = D012 (breaking)
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
  useActivity?: boolean; // D010: optional, default false; lets matching use my Groups, Events, friends, post topics
  eventSignals?: boolean; // v3: optional, default false; lets event interest, nudges and custom-event invites use me
}
/**
 * D010, PRIVATE (self + privacy + formation). Stored only while useActivity is on.
 * Topics are derived by code from my own posts/comments with a fixed safe
 * allowlist; the text itself is never stored, sent to Muse or shown to anyone.
 */
export interface ActivitySignals {
  profileId: Id | null; // opaque Facebook-side id, used only to count mutual friends
  groupIds: Id[]; eventIds: Id[]; friendIds: Id[];
  topics: string[]; // allowlisted labels only; never sensitive categories
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
  answeredToday?: number; // v3: distinct players who answered today; the only count on daily screens. Optional until the web client sends it (Will)
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
/** @deprecated 3.0.0 removes the guess (PUT /cycles/:id/guess). */
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
  /** @deprecated since 3.0.0, constellations have no name or shape and v3 views never carry them. Removed with M5. */
  name: string;
  shapeId: string; colorId: string; // @deprecated 3.0.0
  baselineAgrees: boolean; // keyword baseline grouped these members the same way
  closeness?: { a: Id; b: Id; score: number }[]; // D009, PRIVATE server-only pairwise 0..1 incl. D010 boosts; banded before output
  memberContext?: Record<Id, ConstellationContext>; // D010, PRIVATE: per member, served only to that member
}
/** @deprecated 3.0.0 removes Sky statistics (SkyTheme, SkyStats, M8). v3 uses SkyStarsView + MySkyView. */
export interface SkyTheme { // PUBLIC aggregate; rendered only if count >= threshold
  themeId: Id; label: string; count: number;
  actualPercent: number;       // count / eligible players
  guessedPercentMedian: number; // from PrevalenceGuess of members of this theme
}
/** @deprecated 3.0.0, see SkyTheme. */
export interface SkyStats { // PUBLIC; Rishi computes, Kai serves + renders
  cycleId: Id; threshold: number; // 3 demo, 25 production
  eligiblePlayers: number; constellations: number; mutualReveals: number;
  themes: SkyTheme[]; // already filtered by threshold
  suppressedThemes: number; // count only, no labels
  headlines: string[]; // M8, numbers checked against server counts
  syntheticSignals: SyntheticSignal[]; // labeled, never merged into counts
  evidence: MuseCallEvidence[];
}
/** @deprecated 3.0.0: not on any player-facing path. Aggregate-only synthetic signal. */
export interface SyntheticSignal { // PUBLIC
  signalId: Id; label: string; percent: number; sampleSize: number; source: "synthetic";
}

// ---- Anonymous chat, moderation, reveal (Kai; moderation calls Patrik) --
/** D009: closeness to the viewer, banded by code. Never a raw score. */
export type Brightness = "bright" | "mid" | "faint";
export interface AnonymousHandle { // PUBLIC to room members
  roomId: Id; handle: string; // e.g. "Star 3"; never derived from name
  starColor: string; isSelf: boolean;
  brightness?: Brightness; // D009; omitted when isSelf
}
/** D010, PUBLIC to the viewing member: counts only, never which star shares what. */
export interface ConstellationContext {
  sharedGroupStars: number; // other members in at least one of my Groups
  alreadyFriends: number;   // other members already my friends
  sameEventStars: number;   // other members interested in an event I'm interested in
}
export type RoomStatus = "open" | "expired" | "closed";
/** v3: no title or name; handles derive from the room-local index, never the sky star index (R1). */
export interface ChatRoom { // PUBLIC to members
  roomId: Id; constellationId: Id; cycleId: Id;
  status: RoomStatus; opensAt: IsoTime; expiresAt: IsoTime;
  members: AnonymousHandle[];
  context?: ConstellationContext; // D010, per viewer
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
/** @deprecated 3.0.0: room-posted nudges are removed; use EventNudgeView. */
export interface EventNudge { // PUBLIC to room members, posted as a muse_nudge message
  nudgeId: Id; constellationId: Id; title: string; placeId: Id;
  timeWindow: TimeWindow; why: string; // passes OutputGuard; never quotes answers
  minAttendees: 3; evidence: MuseCallEvidence;
}

// ---- v3: daily constellations, sky, main constellation (Rishi produces) --
/** v3 numbers. Code enforces them; every view type below relies on them. */
export const V3 = {
  maxDailyConstellations: 3,  // per player per day
  minVisibleConstellation: 3, // R2: nothing under 3 members is ever shown, any degree
  dailyConstellationMaxStars: 12,
  mainSize: { min: 3, max: 5 }, // Sunday main constellation incl. the viewer
  secondDegreeMinEligible: 30, // R2: below this, secondDegree is []
  secondDegreeMaxConstellations: 40, secondDegreeMaxStars: 3000,
  skyStars: 10000,
  eventBucketMin: 3, // never show a count under 3
  chatHours: 24,
} as const;
export type DayColorId = "blue" | "teal" | "green" | "amber" | "rose"; // Mon..Fri
export const DAY_COLORS: Record<CycleDay, DayColorId> = { 1: "blue", 2: "teal", 3: "green", 4: "amber", 5: "rose" };
/** A star is an index into one week's sky, re-randomized every cycle. Never a player id. */
export type StarIndex = number;
/** R1: an index local to one chat room / main constellation. Drawn fresh per room; never equals the sky StarIndex. */
export type RoomIndex = number;
export interface SkyPoint { index: StarIndex; x: number; y: number } // x, y in 0..1

/** GET /cycles/:id/days/:day/constellations (S5). PUBLIC to the viewer, who answered that day. */
export type DailyPlacement = "pending" | "ready" | "final"; // final after day close
export interface DailyConstellationView {
  constellationId: Id; // opaque; no name, no label
  starIndices: StarIndex[]; // includes myStarIndex; 3..dailyConstellationMaxStars
  brightness: Brightness; // per viewer, banded by code (D009)
  anchors: SkyPoint[];
}
export interface DailyConstellationsView {
  day: CycleDay; colorId: DayColorId;
  answeredToday: number; // the only count on daily screens
  placement: DailyPlacement;
  myStarIndex: StarIndex;
  constellations: DailyConstellationView[]; // 0..V3.maxDailyConstellations; [] is valid
}

/** GET /cycles/:id/sky/stars (S9): same for all viewers; positions reveal nothing about membership. */
export interface SkyStarsView {
  weekSeed: string; count: number;
  positions: string; // base64 Int16Array [x0,y0,x1,y1,...] on a 0..32767 grid
}
/** GET /cycles/:id/sky/mine (S9). Star indices only. */
export interface MySkyView {
  myStarIndex: StarIndex;
  mine: { constellationId: Id; day: CycleDay; colorId: DayColorId; starIndices: StarIndex[] }[];
  /** Drawn at low opacity. [] when fewer than V3.secondDegreeMinEligible players are eligible (R2). */
  secondDegree: { constellationId: Id; viaStarIndex: StarIndex; starIndices: StarIndex[] }[];
}

/** S10: one candidate connection the algorithm evaluated for this viewer. No scores, no reasons. */
export interface FormationAttempt {
  seq: number;
  fromStarIndex: StarIndex; toStarIndex: StarIndex; // the viewer's own stars or their second-degree neighbours only
  outcome: "tried" | "kept" | "dropped";
}
export type ProgressPhase = "queued" | "running" | "done";
/** GET /cycles/:id/formation/progress and the formation.progress stream slice. */
export interface ProgressEvent {
  phase: ProgressPhase; step: number; totalSteps: number;
  attempts: FormationAttempt[];
  /** "trace" = real candidate pairs the matcher evaluated for this viewer, paced for display.
   *  "visualization" = labeled illustration (trace recording cut or stream dropped); UI must say so. */
  source: "trace" | "visualization";
  isVisualization: boolean; // always equals (source === "visualization")
}

/** GET /cycles/:id/main (S11). R1: room-local indices, never the sky StarIndex. */
export type MainConstellationReason = "no_match" | "opted_out" | "no_answers";
export interface MainConstellationView {
  constellationId: Id; roomId: Id;
  myRoomIndex: RoomIndex;
  roomIndices: RoomIndex[]; // 3..5 including me (V3.mainSize)
  anchors: { index: RoomIndex; t: number }[]; // t in 0..1 along the Meta-logo path, one per member
  brightness: Record<number, Brightness>; // keyed by room index; banded per viewer
  revealedAt: IsoTime; roomExpiresAt: IsoTime; // revealedAt + V3.chatHours
}
/** `main: null` carries only an enum reason, never detail. */
export interface MainConstellationResponse { main: MainConstellationView | null; reason: MainConstellationReason | null }

// ---- v3: events and custom events ----------------------------------------
/** Bucketed, only from 3 up, recomputed hourly only (R3). Never an exact count. */
export type InterestBucket = "3-5" | "6-9" | "10+";
export type ConstellationInterestBucket = "none" | InterestBucket;
export interface EventView { // PUBLIC; approved catalog only (D015 allowlist) or an approved custom event
  eventId: Id; title: string; placeId: Id; startsAt: IsoTime; endsAt: IsoTime;
  constellationInterestBucket: ConstellationInterestBucket; // computed per viewer by Rishi
  myInterest: boolean;
  kind: "catalog" | "custom";
}
export interface EventNudgeView { // PUBLIC to the viewer; delivered with a delay (R3); max 2 per week, 1 per 48 h
  nudgeId: Id; eventId: Id;
  copy: string; // Adam M7, templated, OutputGuard + M10 checked; never names, never exact counts
  interestBucket: InterestBucket; expiresAt: IsoTime;
}
/** Operator-gated M7 extension (task "custom_event"). Input is aggregate only: no ids, no answers. */
export interface CustomEventProposalIn {
  clusterSize: number; interestTags: ActivityTopic[]; area: string; // city level
  windows: TimeWindow[]; venues: Venue[];
}
export interface CustomEventProposal { // operator only until approved
  proposalId: Id; clusterSize: number; title: string; why: string; // why = tags only, no player text
  placeId: Id; // approved public venue
  timeWindow: TimeWindow; evidence: MuseCallEvidence;
  status: "pending" | "approved" | "rejected";
}
export type CustomEventProposalOut = Pick<CustomEventProposal, "title" | "why" | "placeId" | "timeWindow">;
export interface Invite { // own only; no RSVP counts, no attendee list
  inviteId: Id; event: EventView; rsvp: "none" | "going" | "not_going";
  status: "pending" | "confirmed" | "cancelled"; confirmAtCount: 3;
}

// ---- Realtime (Kai) -----------------------------------------------------
export type StreamEvent =
  | { type: "cycle.updated"; seq: number; cycle: WeeklyCycle }
  | { type: "constellation.revealed"; seq: number; roomId: Id }
  | { type: "chat.message"; seq: number; message: ChatMessage }
  | { type: "chat.moderated"; seq: number; messageId: Id; moderation: ModerationState }
  | { type: "reveal.mutual"; seq: number; reveal: MutualReveal }
  | { type: "room.expired"; seq: number; roomId: Id }
  | { type: "sky.updated"; seq: number; cycleId: Id } // @deprecated 3.0.0 (no Sky stats)
  // v3
  | { type: "daily.updated"; seq: number; day: CycleDay }
  | { type: "day.closed"; seq: number; day: CycleDay }
  | { type: "formation.progress"; seq: number; progress: ProgressEvent }
  | { type: "main.revealed"; seq: number; roomId: Id }
  | { type: "event.nudge"; seq: number; nudgeId: Id }
  | { type: "invite.created" | "invite.updated"; seq: number; inviteId: Id };

// ---- Evidence and errors ------------------------------------------------
export interface ModelEvidence {
  model: string; source: "live" | "replay"; generatedAt: IsoTime; latencyMs: number;
}
export type MuseCallType = "M1" | "M2" | "M3" | "M4" | "M5" | "M6" | "M7" | "M8" | "M9" | "M10";
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
/** constellation_naming (M5) and sky_narration (M8) are DEPRECATED in 3.0.0: the v3 pipeline never calls
 *  them. They stay in the union and registry until the follow-up PR deletes them with their code. */
export type MuseTask =
  | "safety_screen" | "clarify" | "theme_discovery" | "constellation_formation"
  | "constellation_naming" | "question_generation" | "event_nudge" | "sky_narration"
  | "activity_classification" | "sensitivity_screen"; // M9, M10 (D014)
export interface PromptText { id: string; text: string; weight?: number } // id random per call
/** D014: an answer sent to M3/M4 says which question it replies to ("nobody" means
 *  different things under different questions). Optional for migration. */
export interface AnswerText extends PromptText { questionId?: string }

export interface M1In { text: PromptText; subjectType: "answer" | "chat_message" } // Patrik
export interface M1Out { flag: SafetyLevel; reason: string }
export interface M2In { question: string; answer: PromptText } // Adam, called by Will
export interface M2Out { needsFollowup: boolean; question: string }
export interface M3In { answers: AnswerText[]; questions: { questionId: string; text: string }[] } // Rishi
export interface M3Out { themes: { id: string; label: string; description: string; memberIds: string[] }[] }
export interface M4In { // Rishi
  themes: M3Out["themes"]; answers: AnswerText[]; blockedPairs: [string, string][];
  questions?: { questionId: string; text: string }[]; // D014
  /** D014, D010 opt-in only: server-computed soft hints (pairs of random refs and how
   *  many interests, Groups or Events they share). No topics or ids reach Muse.
   *  Meaning comes first; affinity may only break ties. */
  affinity?: { memberIds: [string, string]; shared: number }[];
}
export interface M4Out { constellations: { memberIds: string[]; sharedMeaning: string; confidence: number }[] }
/** @deprecated 3.0.0 (nothing has a name). */
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
/** @deprecated 3.0.0 (Sky stats removed). */
export interface M8In { // Rishi; counts only
  eligiblePlayers: number; constellations: number;
  themes: { label: string; count: number; actualPercent: number; guessedPercentMedian: number }[];
}
export interface M8Out { headlines: string[] } // every number must equal an input number
/** D014 M9, Patrik: a player's own opted-in posts/comments (and "liked: ..." items),
 *  transient, never stored or logged; only validated labels are kept. */
export type ActivityTopic =
  | "ai" | "coding" | "design" | "music" | "gaming" | "vr" | "study" | "coffee"
  | "food" | "outdoors" | "sports" | "film" | "art" | "books";
export interface M9In { texts: { id: string; text: string }[] } // id random per call, 1-10 texts
export interface M9Out {
  results: { id: string; sensitive: boolean;
    labels: { topic: ActivityTopic; stance: "positive" | "neutral" | "negative" }[] }[]; // <= 3 labels
}
/** D014 M10, Patrik: public game text (constellation names, Sky labels and headlines,
 *  nudges, generated questions) -> one category; code blocks anything but "none". */
export type SensitivityCategory =
  | "none" | "health" | "mental_health" | "sexuality" | "religion" | "money"
  | "family" | "location" | "identity" | "substance" | "violence";
export interface M10In { items: { id: string; text: string }[] } // 1-40 items
export interface M10Out { results: { id: string; category: SensitivityCategory }[] }

export interface MuseJobMap {
  safety_screen: { in: M1In; out: M1Out };
  clarify: { in: M2In; out: M2Out };
  theme_discovery: { in: M3In; out: M3Out };
  constellation_formation: { in: M4In; out: M4Out };
  constellation_naming: { in: M5In; out: M5Out };
  question_generation: { in: M6In; out: M6Out };
  event_nudge: { in: M7In; out: M7Out };
  sky_narration: { in: M8In; out: M8Out };
  activity_classification: { in: M9In; out: M9Out };
  sensitivity_screen: { in: M10In; out: M10Out };
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
  formationSnapshot(cycleId: Id): Promise<{
    answers: AnswerText[]; idMap: Record<string, Id>; blockedPairs: [Id, Id][];
    questions?: { questionId: string; text: string }[]; // D014: when the cycle's question texts are available
    activity?: Record<string, ActivitySignals>; // D010: by ref, only for players with useActivity
  }>;
  screen(text: string, subjectType: "answer" | "chat_message"): Promise<SafetyFlag["flag"]>;
}
export interface OutputGuard { // Patrik; applied to every Muse text and every chat message
  check(text: string, againstAnswers: string[]): {
    ok: boolean; reasons: ("quote_5_words" | "sensitive_term" | "pii" | "contact_info")[];
  };
}
/** Rishi, v3: formation producers. Kai runs the jobs and commits under the privacy guard. Results are counts
 *  and opaque ids only; views reach players through the read routes, as star or room indices. */
export type FormationFailure = { status: "failed"; error: ApiError["error"] };
export interface FormationPort {
  /** Instant placement on answer accept: baseline matcher only, no Muse. Up to V3.maxDailyConstellations. */
  dailyPlace(cycleId: Id, day: CycleDay, playerRef: string): Promise<
    { status: "ok"; placement: DailyPlacement; constellationIds: Id[] } | FormationFailure>;
  /** Day close (batch): Muse M3 may propose tags, code assigns best 1-2 per answer, a tag with 3+ players becomes a
   *  constellation, blocks respected, labeled "Fallback grouping" internally on failure. Updates the week graph. */
  closeDay(cycleId: Id, day: CycleDay): Promise<
    { status: "ok"; constellations: number; unplaced: number; evidence: MuseCallEvidence[] } | FormationFailure>;
  /** Co-membership graph for the week: edge weight = shared constellations. Server only; ids never leave. */
  weekGraph(cycleId: Id): Promise<{ status: "ok"; players: number; edges: number } | FormationFailure>;
  /** Sunday main constellations: 3-5, one per player, M4 on the bounded candidate set. Views use room indices (R1). */
  mainConstellation(cycleId: Id): Promise<
    { status: "ok"; groups: number; unplaced: number; evidence: MuseCallEvidence[] } | FormationFailure>;
  /** Saturday layout: week-seeded positions; secondDegree is false below V3.secondDegreeMinEligible (R2). */
  skyLayout(cycleId: Id): Promise<
    { status: "ok"; stars: SkyStarsView; eligiblePlayers: number; secondDegree: boolean } | FormationFailure>;
}
/** @deprecated 3.0.0: replaced by FormationPort.mainConstellation. The Python MatchingPort keeps form/computeSky
 *  until Kai migrates; the follow-up PR deletes them. */
export interface LegacyFormationPort {
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
  openRooms(cycleId: Id, constellations: Constellation[]): Promise<ChatRoom[]>; // v3: Kai builds rooms from MainConstellationView groups
  postSystem(roomId: Id, message: Omit<ChatMessage, "messageId" | "createdAt" | "moderation">): Promise<ChatMessage>;
  expire(cycleId: Id): Promise<number>;
}
