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
