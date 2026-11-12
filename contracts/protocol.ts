/**
 * Group Quests wire contract v1.0.0.
 * Definitions only: consumers MUST implement runtime validation.
 * JSON keys remain camelCase across TypeScript and Python.
 * Private types are server-side wire shapes, never browser-wide state.
 */
export const CONTRACT_VERSION = "1.0.0" as const;
export type Id = string;
export type IsoTime = string; // RFC3339 UTC; retain IANA zone for display
export type Mode = "live" | "fixture" | "replay";
export interface Window { start: IsoTime; end: IsoTime }
export interface Context {
  requestId: Id;
  contractVersion: typeof CONTRACT_VERSION;
  mode: Mode;
}
export interface ModelEvidence {
  model: string;
  source: "live" | "replay";
  generatedAt: IsoTime;
  latencyMs: number;
}
export interface PrivateIntent {
  participantId: Id; communityId: Id; intentVersion: number;
  goal: string; interests: string[]; areaId: Id; timeZone: string;
  availability: Window[]; maxBudgetMinor: number; currency: string;
  maxDurationMinutes: number; groupPreference: "small";
  consentVersion: number; confirmedAt: IsoTime;
}
export interface PublicParticipant {
  participantId: Id; displayName: string; publicInterests: string[];
  isSynthetic: boolean;
}
export interface Consent {
  participantId: Id; communityId: Id; version: number;
  matching: boolean; modelProcessing: boolean; publicInterests: boolean;
  revokedAt: IsoTime | null;
}
export interface Candidate {
  // Internal only; privacy layer has already authorized/minimized this snapshot.
  intent: PrivateIntent; publicProfile: PublicParticipant;
}
export interface MatchInput {
  context: Context; communityId: Id; requesterId: Id;
  candidates: Candidate[]; minimumSize: 3; maximumSize: 5;
}
export interface MemberVersion {
  participantId: Id; intentVersion: number; consentVersion: number;
}
export interface GroupProposal {
  proposalId: Id; communityId: Id; revision: number;
  memberIds: Id[]; memberVersions: MemberVersion[];
  feasibleWindows: Window[];
  sharedInterests: string[];
  publicRationale: string;
  evidence: ModelEvidence;
}
export type MatchResult =
  | { status: "matched"; proposal: GroupProposal }
  | { status: "no_match"; reason: "too_few" | "no_common_time" | "constraints";
      suggestions: string[] };
export interface Venue {
  venueId: Id; name: string; areaId: Id; publicAddress: string;
  isPublic: true; openingWindows: Window[];
}
export interface PlanInput {
  context: Context; proposal: GroupProposal;
  participants: Candidate[]; venues: Venue[];
  previousPlan?: QuestPlan; changeSummary?: string;
}
export interface QuestPlan {
  planId: Id; proposalId: Id; revision: number; basedOnRevision: number | null;
  memberVersions: MemberVersion[];
  title: string; activity: string; collaborationTask: string;
  venueId: Id; start: IsoTime; end: IsoTime; timeZone: string;
  costPerPersonMinor: number; currency: string;
  minimumSize: 3; maximumSize: 5;
  publicRationale: string; opener: string;
  evidence: ModelEvidence;
}
export type PlanResult =
  | { status: "proposed"; plan: QuestPlan }
  | { status: "needs_input"; fields: string[]; question: string }
  | { status: "no_feasible_plan"; reason: string };
export interface Acceptance {
  questId: Id; participantId: Id; revision: number;
  choice: "accept" | "decline"; recordedAt: IsoTime;
}
export type QuestStatus =
  | "forming" | "proposed" | "planning" | "scheduled"
  | "revision_pending" | "completed" | "cancelled";
export interface QuestSnapshot {
  questId: Id; communityId: Id; revision: number; status: QuestStatus;
  members: PublicParticipant[]; acceptedCount: number;
  capacity: 5; minimumSize: 3; event: EventRecord | null;
}
export interface EventRecord {
  eventId: Id; questId: Id; planId: Id; revision: number;
  status: "scheduled" | "cancelled" | "completed";
  title: string; venueId: Id; start: IsoTime; end: IsoTime;
  acceptedMemberIds: Id[]; conversationId: Id;
}
export interface ConversationMessage {
  messageId: Id; conversationId: Id; createdAt: IsoTime;
  sender: { kind: "participant"; participantId: Id } | { kind: "assistant" };
  text: string;
}
export interface WorkflowEvent {
  eventId: Id; questId: Id; sequence: number; revision: number;
  type: "member.accepted" | "member.left" | "plan.proposed"
    | "event.created" | "plan.revised" | "quest.cancelled" | "message.created";
  occurredAt: IsoTime;
  // Payload is a public snapshot or message, never a PrivateIntent.
  snapshot?: QuestSnapshot;
  message?: ConversationMessage;
}
export interface ContinuationInput {
  context: Context; questId: Id; priorPlan: QuestPlan;
  feedback: { participantId: Id; attended: boolean | null; wantsReturn: boolean }[];
  simulateTimeSkip: boolean;
}
export interface Continuation {
  questId: Id; proposedHostId: Id | null;
  invitationText: string; nextActivity: string; evidence: ModelEvidence;
}
export type ErrorCode =
  | "INVALID_INPUT" | "UNAUTHENTICATED" | "FORBIDDEN" | "NOT_FOUND"
  | "CONSENT_REQUIRED" | "STALE_REVISION" | "CAPACITY_REACHED"
  | "PROVIDER_UNAVAILABLE" | "RATE_LIMITED" | "IDEMPOTENCY_CONFLICT";
export interface ApiError {
  error: { code: ErrorCode; message: string; requestId: Id; retryable: boolean };
}
/** Provider-independent service port. No assumption about Muse API shape. */
export interface MusePort {
  generate(input: {
    task: "extract_intent" | "rank_group" | "plan" | "revise" | "continue";
    requestId: Id; promptVersion: string; payload: unknown;
    signal?: AbortSignal;
  }): Promise<{ output: unknown; evidence: ModelEvidence }>;
}
/** These are boundary signatures, not implemented functions. */
export interface MatchingPort { match(input: MatchInput): Promise<MatchResult> }
export interface PlanningPort {
  plan(input: PlanInput): Promise<PlanResult>;
  revise(input: PlanInput): Promise<PlanResult>;
  continue(input: ContinuationInput): Promise<Continuation>;
}

/* ---------------------------------------------------------------------------
 * PROPOSED (docs/DECISIONS.md D005) — additive, pending Will + Patrik ACK.
 * Not part of v1.0.0 until acknowledged; CONTRACT_VERSION is unchanged.
 * Producer: Adam (server/planning). Consumers: Will (onboarding UI), Patrik
 * (PUT /intents/me receives the confirmed copy).
 * POST /intents/extract  body: { transcript: string (1..2000), communityId: Id }
 * ------------------------------------------------------------------------- */
export type IntentField =
  | "goal" | "interests" | "areaId" | "availability"
  | "maxBudgetMinor" | "maxDurationMinutes";
/** Private, unconfirmed draft. No identity, consent or version fields. */
export interface IntentDraft {
  communityId: Id;
  goal: string | null; interests: string[]; areaId: Id | null;
  timeZone: string;            // community default; user may edit
  availability: Window[];      // empty when not stated
  maxBudgetMinor: number | null; currency: string;
  maxDurationMinutes: number | null; groupPreference: "small";
}
export interface ExtractionResult {
  status: "draft";
  draft: IntentDraft;
  missingFields: IntentField[];
  questions: { field: IntentField; question: string }[];
  evidence: ModelEvidence;
}

/* ---------------------------------------------------------------------------
 * PROPOSED (docs/DECISIONS.md D008) — target contract 1.1.0, pending ACK from
 * Will, Patrik, Kai and Rishi. Not part of v1.0.0; CONTRACT_VERSION unchanged.
 * Producer: Adam (server/planning). Examples: contracts/examples/1.1.0/.
 * Python validators: server/planning/wire.py ("PROPOSED (D008)").
 * ------------------------------------------------------------------------- */
export type Energy = "low" | "medium" | "high";
export type SocialComfort = "quiet" | "balanced" | "outgoing";
export type PreferenceField =
  | "availability" | "maxBudgetMinor" | "areaId"
  | "interests" | "energy" | "socialComfort";

/** Private draft of what a member is comfortable with. Never an activity choice. */
export interface PreferenceProfile {
  communityId: Id;
  availability: Window[];          // [] when not stated
  timeZone: string;                // community default
  maxBudgetMinor: number | null;   // per-person ceiling; code enforces it everywhere
  currency: string;                // community currency
  areaId: Id | null;               // community allowlist only
  interests: string[];             // things they enjoy, 0..8
  avoid: string[];                 // private dislikes ("bars"), 0..5; never public
  energy: Energy | null;
  socialComfort: SocialComfort | null;
  openToNew: boolean | null;
}
/** POST /preferences/extract. A request carrying followUp never receives another question. */
export interface PreferenceExtractionRequest {
  communityId: Id;
  transcript: string;              // 1..2000; voice transcript or typed text
  followUp?: { field: PreferenceField; answer: string; previous: PreferenceProfile };
}
export interface PreferenceExtractionResult {
  status: "needs_follow_up" | "ready_to_confirm";
  profile: PreferenceProfile;
  missingFields: PreferenceField[];
  followUp: { field: PreferenceField; question: string } | null; // non-null iff needs_follow_up
  evidence: ModelEvidence;
}
/** Optional 1.1 extension of Candidate (Patrik's snapshot): non-public traits for matching/creation. */
export interface PreferenceTraits {
  energy: Energy | null; socialComfort: SocialComfort | null;
  avoid: string[]; openToNew: boolean | null;
}
// Candidate 1.1 = Candidate & { preferences?: PreferenceTraits }

export type OpportunitySource = "venue_offer" | "group_event" | "member_idea" | "muse_created";
/** Kai owns storage and the full union; Adam produces source "muse_created". */
export interface Opportunity {
  opportunityId: Id; communityId: Id; source: OpportunitySource;
  title: string; activity: string; collaborationTask: string;
  venueId: Id; window: Window; timeZone: string;
  costPerPersonMinor: number; currency: string;
  minimumSize: 3; maximumSize: 5;
  publicRationale: string;         // built by code from allowlisted facts
  isSimulated: boolean;            // true for simulated venue businesses
  evidence: ModelEvidence | null;  // null only for non-model sources
}
export interface CreateEventInput {
  context: Context; communityId: Id;
  candidates: Candidate[];         // 3..50 authorized snapshots (Candidate 1.1)
  venues: Venue[];                 // approved catalog only
}
export type CreateEventResult =
  | { status: "created"; opportunity: Opportunity; eligibleMemberCount: number }
  | { status: "no_fit"; reason: "too_few_overlap" | "no_open_venue" | "budget" };

/** The ONLY facts the (simulated) venue assistant receives. No identities, no individual budgets. */
export interface VenueBrief {
  negotiationId: Id; venueId: Id; activity: string;
  groupSize: number; window: Window;
  totalBudgetMinor: number; currency: string;   // groupSize x lowest member ceiling
}
export interface VenueOffer {
  negotiationId: Id; round: number; venueId: Id;
  action: "offer" | "final_offer" | "decline";
  window: Window; groupSize: number;
  totalPriceMinor: number; currency: string;
  terms: string;                   // public; validated like other public text
  isSimulated: true; evidence: ModelEvidence;
}
export interface Counteroffer {
  negotiationId: Id; round: number;
  action: "counter" | "accept" | "walk_away";
  totalPriceMinor: number; currency: string; window: Window;
  message: string;                 // sent to the venue; validated public text
  evidence: ModelEvidence;
}
export type NegotiationTurn =
  | { by: "venue"; offer: VenueOffer }
  | { by: "group_agent"; counter: Counteroffer };
/** Agreed terms awaiting EVERY member's approval. Nothing is booked or paid here. */
export interface Deal {
  dealId: Id; negotiationId: Id; opportunityId: Id; venueId: Id;
  window: Window; groupSize: number;
  totalPriceMinor: number; perPersonMinor: number; currency: string;
  terms: string; rounds: number;
  status: "awaiting_approval";     // Kai owns later transitions
  isSimulated: true;
  evidence: ModelEvidence;
}
export interface NegotiationInput {
  context: Context; negotiationId: Id; opportunity: Opportunity;
  participants: Candidate[];       // 3..5, server-side only; never sent to the venue
  maxRounds: number;               // 1..4
}
export type NegotiationResult =
  | { status: "deal"; deal: Deal; turns: NegotiationTurn[] }
  | { status: "no_deal"; reason: "over_budget" | "venue_declined" | "rounds_exhausted";
      turns: NegotiationTurn[] };

export interface RewardOption {
  rewardOptionId: Id; label: string; sponsor: "venue" | "group_quests";
  venueId: Id | null; isSimulated: true;
}
export interface Reward {
  rewardId: Id; rewardOptionId: Id; label: string;
  sponsor: "venue" | "group_quests"; venueId: Id | null; isSimulated: true;
}
export interface ChallengeInput {
  context: Context; questId: Id; event: EventRecord; priorPlan: QuestPlan;
  feedback: { participantId: Id; attended: boolean | null; wantsReturn: boolean }[];
  rewardOptions: RewardOption[];   // approved list; Muse may pick one or none
  simulateTimeSkip: boolean;
}
/** Post-meetup challenge. Goal metric is code-verifiable; Kai updates progress. */
export interface Challenge {
  challengeId: Id; questId: Id; basedOnEventId: Id;
  title: string; description: string;
  goal: { metric: "sessions_together"; target: number };  // 2..6
  dueBy: IsoTime;
  progress: { completed: number; target: number };
  reward: Reward | null;
  evidence: ModelEvidence;
}
/** Additional MusePort tasks (allowlisted in server/providers/port.py). */
export type MuseTaskV11 =
  | "extract_preferences" | "create_event" | "negotiate" | "venue_persona" | "challenge";
export interface PlanningPortV11 extends PlanningPort {
  extractPreferences(input: PreferenceExtractionRequest): Promise<PreferenceExtractionResult>;
  createEvent(input: CreateEventInput): Promise<CreateEventResult>;
  negotiate(input: NegotiationInput): Promise<NegotiationResult>;
  challenge(input: ChallengeInput): Promise<Challenge>;
}
