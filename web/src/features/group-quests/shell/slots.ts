/**
 * Feature component integration contract (Will -> every UI owner).
 * Each owner exports a component matching one slot's props from their own
 * directory and registers it in `featureSlots` with a one-line PR. The shell
 * never implements another owner's business logic: an empty slot renders an
 * explicit "not integrated" state instead of a fake result.
 *
 * Proposed in docs/handoffs/will.md; owners ACK or request changes there.
 */
import type { ComponentType } from "react";
import type { Consent, Id, Mode } from "../../../../../contracts/protocol";
import type { AcceptanceAck } from "./useFirstActionTimer";

interface SlotBase {
  communityId: Id;
  /** Server-selected mode; components must label fixture/replay output. */
  mode: Mode;
}

/** Patrik: session check, community opt-in, consent toggles. */
export interface PrivacySlotProps extends SlotBase {
  /** Report current consent; null when absent, revoked or unauthenticated. */
  onConsentChange: (consent: Consent | null) => void;
}

/** Rishi: request a match for the confirmed intent and show the proposal. */
export interface MatchingSlotProps extends SlotBase {
  confirmedIntentVersion: number;
  /** Called after Kai's POST /quests returns the forming quest. */
  onQuestCreated: (questId: Id) => void;
}

/** Adam: show the proposed/revised plan for the quest. */
export interface PlanningSlotProps extends SlotBase {
  questId: Id;
}

/** Kai: acceptance, event card, conversation and stream. */
export interface EventsSlotProps extends SlotBase {
  questId: Id;
  /** Call once the server acknowledges the actor's persisted acceptance. */
  onAccepted: (ack: AcceptanceAck) => void;
}

export interface GroupQuestsSlots {
  privacy?: ComponentType<PrivacySlotProps>;
  matching?: ComponentType<MatchingSlotProps>;
  planning?: ComponentType<PlanningSlotProps>;
  events?: ComponentType<EventsSlotProps>;
}

/** Registration point. Owners add their component here via PR. */
export const featureSlots: GroupQuestsSlots = {};
