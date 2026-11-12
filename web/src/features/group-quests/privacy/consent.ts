import type { Consent } from "../../../../../contracts/protocol";
import type { ConsentToggles } from "./client";

export const CONSENT_KEYS: (keyof ConsentToggles)[] = ["matching", "modelProcessing", "publicInterests"];

export const CONSENT_COPY: Record<keyof ConsentToggles, { label: string; detail: string }> = {
  matching: {
    label: "Find me a group",
    detail: "Lets Group Quests consider you for small groups of 3–5 in this community.",
  },
  modelProcessing: {
    label: "Let Muse read my preferences",
    detail: "The Muse model reads your confirmed goal, interests, times and budget to suggest groups and plans. Required for matching.",
  },
  publicInterests: {
    label: "Show my interests to my group",
    detail: "When off, group members see only your display name.",
  },
};

export function isMatchable(consent: Pick<Consent, "matching" | "modelProcessing">): boolean {
  return consent.matching && consent.modelProcessing;
}

export function formatMoney(minor: number, currency: string): string {
  if (minor === 0) return "Free only";
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(minor / 100) + " max";
}
