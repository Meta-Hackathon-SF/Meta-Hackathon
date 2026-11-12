/**
 * Onboarding-side views of the shared wire contract (contracts/protocol.ts).
 * Shapes are derived from the shared types instead of redefined. The only
 * additions are UI port signatures and the extraction draft, which API.md
 * describes ("private draft plus missingFields") but protocol.ts does not yet
 * declare. See docs/handoffs/will.md for the open request to Adam.
 */
import type {
  ErrorCode,
  Id,
  Mode,
  ModelEvidence,
  PrivateIntent,
} from "../../../../../contracts/protocol";

/** Fields a person confirms during onboarding, in display order. */
export const INTENT_FIELDS = [
  "goal",
  "interests",
  "areaId",
  "availability",
  "maxBudgetMinor",
  "maxDurationMinutes",
] as const;
export type IntentField = (typeof INTENT_FIELDS)[number];

/** Partial private intent produced by extraction. Absent means unknown. */
export type IntentDraft = Partial<
  Pick<
    PrivateIntent,
    | "goal"
    | "interests"
    | "areaId"
    | "availability"
    | "maxBudgetMinor"
    | "currency"
    | "maxDurationMinutes"
  >
>;

export interface IntentExtraction {
  draft: IntentDraft;
  /** Required fields extraction could not determine; the UI asks for each. */
  missingFields: IntentField[];
  /** Present for model output; absent for fixture extraction. */
  evidence: ModelEvidence | null;
}

/**
 * Body for PUT /api/v1/intents/me (Patrik). participantId comes from the
 * server-verified session; intentVersion, consentVersion and confirmedAt are
 * server-assigned. expectedVersion is 0 when no confirmed intent exists yet.
 */
export type ConfirmedIntentSubmission = Pick<
  PrivateIntent,
  | "communityId"
  | "goal"
  | "interests"
  | "areaId"
  | "timeZone"
  | "availability"
  | "maxBudgetMinor"
  | "currency"
  | "maxDurationMinutes"
  | "groupPreference"
> & { expectedVersion: number };

export type OnboardingErrorCode = ErrorCode | "NETWORK" | "INVALID_RESPONSE";

export class OnboardingError extends Error {
  readonly code: OnboardingErrorCode;
  readonly retryable: boolean;
  readonly requestId: Id | null;
  constructor(
    code: OnboardingErrorCode,
    message: string,
    retryable: boolean,
    requestId: Id | null = null,
  ) {
    super(message);
    this.name = "OnboardingError";
    this.code = code;
    this.retryable = retryable;
    this.requestId = requestId;
  }
}

/**
 * Service port used by the onboarding UI. Implementations: the HTTP adapter
 * (live server) and the fixture adapter (development/tests, labeled in UI).
 * Every call must reject with an AbortError when its signal aborts.
 */
export interface OnboardingPorts {
  /** Server-selected mode label. The UI displays it and never changes it. */
  readonly mode: Mode;
  transcribe(audio: Blob, signal: AbortSignal): Promise<{ transcript: string }>;
  extract(
    input: { transcript: string; communityId: Id },
    signal: AbortSignal,
  ): Promise<IntentExtraction>;
  confirm(
    submission: ConfirmedIntentSubmission,
    options: { signal: AbortSignal; idempotencyKey: string },
  ): Promise<PrivateIntent>;
}

/** Community facts the onboarding form needs. Supplied by the shell. */
export interface OnboardingCommunity {
  communityId: Id;
  name: string;
  currency: string;
  areas: { areaId: Id; name: string }[];
}
