// Wire types come from the shared contract; only types are imported, so no
// runtime code from outside web/ is bundled.
import type {
  ApiError,
  Continuation,
  ExtractionResult,
  Id,
  IntentDraft,
  IntentField,
  IsoTime,
  ModelEvidence,
} from "../../../../../contracts/protocol.ts";

export type { ApiError, Continuation, ExtractionResult, Id, IntentDraft, IntentField, IsoTime, ModelEvidence };

/**
 * Public, allowlisted projection of a QuestPlan for display to group members.
 * Mirrors the planning card DTO requested from Patrik (handoff): it excludes
 * memberVersions and any participant constraint. The opener is delivered as
 * an assistant chat message by Kai, not shown here.
 */
export interface PublicPlanCard {
  planId: Id;
  revision: number;
  basedOnRevision: number | null;
  title: string;
  activity: string;
  collaborationTask: string;
  venue: { venueId: Id; name: string; publicAddress: string };
  start: IsoTime;
  end: IsoTime;
  timeZone: string;
  costPerPersonMinor: number;
  currency: string;
  publicRationale: string;
  evidence: ModelEvidence;
}

/**
 * Which decision the viewer is making. contracts/WORKFLOW.md requires the UI
 * to distinguish joining a quest from confirming its final plan.
 */
export type PlanPhase = "joining" | "confirming_plan" | "reconfirming" | "confirmed";

export type PlanStatusState =
  | { kind: "planning" }
  | { kind: "needs_input"; fields: string[]; question: string }
  | { kind: "no_feasible_plan"; reason: string }
  | { kind: "error"; message: string; retryable: boolean; requestId?: string };
