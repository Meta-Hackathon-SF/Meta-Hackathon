/**
 * Runtime validation for onboarding. TypeScript types are not checked at the
 * network boundary, so every response and every submission passes through
 * these functions.
 */
import type {
  ModelEvidence,
  PrivateIntent,
  Window,
} from "../../../../../contracts/protocol";
import {
  INTENT_FIELDS,
  OnboardingError,
  type ConfirmedIntentSubmission,
  type IntentDraft,
  type IntentExtraction,
  type IntentField,
  type OnboardingCommunity,
} from "./types";

export const LIMITS = {
  transcriptChars: 2000,
  goalChars: 300,
  interests: 8,
  interestChars: 40,
  windows: 6,
  minDurationMinutes: 15,
  maxDurationMinutes: 600,
  maxBudgetMinor: 100_000,
} as const;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const isNonNegativeInt = (value: unknown): value is number =>
  typeof value === "number" && Number.isInteger(value) && value >= 0;
const RFC3339 =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

export function isValidWindow(value: unknown): value is Window {
  if (!isRecord(value)) return false;
  const { start, end } = value;
  if (typeof start !== "string" || typeof end !== "string") return false;
  if (!RFC3339.test(start) || !RFC3339.test(end)) return false;
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  return Number.isFinite(startMs) && Number.isFinite(endMs) && startMs < endMs;
}

function invalid(message: string): never {
  throw new OnboardingError("INVALID_RESPONSE", message, false);
}

function parseEvidence(value: unknown): ModelEvidence | null {
  if (value === undefined || value === null) return null;
  if (
    !isRecord(value) ||
    typeof value.model !== "string" ||
    (value.source !== "live" && value.source !== "replay") ||
    typeof value.generatedAt !== "string" ||
    typeof value.latencyMs !== "number"
  )
    invalid("Extraction evidence is malformed.");
  return {
    model: value.model,
    source: value.source,
    generatedAt: value.generatedAt,
    latencyMs: value.latencyMs,
  };
}

/** Validates an extraction response. Unknown keys are dropped; bad values reject. */
export function parseExtraction(value: unknown): IntentExtraction {
  if (!isRecord(value) || !isRecord(value.draft))
    invalid("Extraction response has no draft.");
  const raw = value.draft;
  const draft: IntentDraft = {};
  if (raw.goal !== undefined) {
    if (typeof raw.goal !== "string") invalid("Draft goal must be text.");
    draft.goal = raw.goal.slice(0, LIMITS.goalChars);
  }
  if (raw.interests !== undefined) {
    if (
      !Array.isArray(raw.interests) ||
      !raw.interests.every((item) => typeof item === "string")
    )
      invalid("Draft interests must be a list of text.");
    draft.interests = (raw.interests as string[])
      .map((item) => item.trim().slice(0, LIMITS.interestChars))
      .filter(Boolean)
      .slice(0, LIMITS.interests);
  }
  if (raw.areaId !== undefined) {
    if (typeof raw.areaId !== "string") invalid("Draft areaId must be text.");
    draft.areaId = raw.areaId;
  }
  if (raw.availability !== undefined) {
    if (
      !Array.isArray(raw.availability) ||
      !raw.availability.every(isValidWindow)
    )
      invalid("Draft availability contains an invalid window.");
    draft.availability = (raw.availability as Window[]).map(({ start, end }) => ({
      start,
      end,
    }));
  }
  if (raw.maxBudgetMinor !== undefined) {
    if (!isNonNegativeInt(raw.maxBudgetMinor))
      invalid("Draft budget must be a nonnegative integer.");
    draft.maxBudgetMinor = raw.maxBudgetMinor;
  }
  if (raw.currency !== undefined) {
    if (typeof raw.currency !== "string") invalid("Draft currency must be text.");
    draft.currency = raw.currency;
  }
  if (raw.maxDurationMinutes !== undefined) {
    if (!isNonNegativeInt(raw.maxDurationMinutes) || raw.maxDurationMinutes === 0)
      invalid("Draft duration must be a positive integer.");
    draft.maxDurationMinutes = raw.maxDurationMinutes;
  }
  const missing = value.missingFields;
  if (!Array.isArray(missing) || !missing.every((f) => typeof f === "string"))
    invalid("Extraction response has no missingFields list.");
  // Unknown field names are ignored rather than rendered.
  const missingFields = (missing as string[]).filter((f): f is IntentField =>
    (INTENT_FIELDS as readonly string[]).includes(f),
  );
  return { draft, missingFields, evidence: parseEvidence(value.evidence) };
}

/** Validates the PrivateIntent returned by PUT /intents/me. */
export function parsePrivateIntent(value: unknown): PrivateIntent {
  if (!isRecord(value)) invalid("Confirmed intent response is malformed.");
  const v = value;
  const ok =
    typeof v.participantId === "string" &&
    typeof v.communityId === "string" &&
    isNonNegativeInt(v.intentVersion) &&
    typeof v.goal === "string" &&
    Array.isArray(v.interests) &&
    v.interests.every((i) => typeof i === "string") &&
    typeof v.areaId === "string" &&
    typeof v.timeZone === "string" &&
    Array.isArray(v.availability) &&
    v.availability.every(isValidWindow) &&
    isNonNegativeInt(v.maxBudgetMinor) &&
    typeof v.currency === "string" &&
    isNonNegativeInt(v.maxDurationMinutes) &&
    v.groupPreference === "small" &&
    isNonNegativeInt(v.consentVersion) &&
    typeof v.confirmedAt === "string";
  if (!ok) invalid("Confirmed intent response is malformed.");
  return v as unknown as PrivateIntent;
}

/* ---------- Form model ---------- */

export interface WindowInput {
  key: string;
  date: string; // YYYY-MM-DD, local to timeZone
  start: string; // HH:MM
  end: string; // HH:MM
}

export interface IntentForm {
  goal: string;
  interests: string[];
  areaId: string;
  availability: WindowInput[];
  budget: string; // major units as typed, e.g. "10" or "7.50"
  durationMinutes: string;
}

export const emptyForm = (): IntentForm => ({
  goal: "",
  interests: [],
  areaId: "",
  availability: [],
  budget: "",
  durationMinutes: "",
});

let windowKeySeed = 0;
export const newWindowKey = () => `window-${++windowKeySeed}`;

const pad = (n: number) => String(n).padStart(2, "0");

/** Converts an extraction draft into editable form values. Unknown stays blank. */
export function formFromDraft(
  draft: IntentDraft,
  community: OnboardingCommunity,
): IntentForm {
  const form = emptyForm();
  form.goal = draft.goal ?? "";
  form.interests = draft.interests ?? [];
  if (draft.areaId && community.areas.some((a) => a.areaId === draft.areaId))
    form.areaId = draft.areaId;
  form.availability = (draft.availability ?? []).map(({ start, end }) => {
    const s = new Date(start);
    const e = new Date(end);
    return {
      key: newWindowKey(),
      date: `${s.getFullYear()}-${pad(s.getMonth() + 1)}-${pad(s.getDate())}`,
      start: `${pad(s.getHours())}:${pad(s.getMinutes())}`,
      end: `${pad(e.getHours())}:${pad(e.getMinutes())}`,
    };
  });
  // Only accept a draft budget expressed in the community's currency.
  if (
    draft.maxBudgetMinor !== undefined &&
    (draft.currency === undefined || draft.currency === community.currency)
  )
    form.budget = formatMinor(draft.maxBudgetMinor);
  if (draft.maxDurationMinutes !== undefined)
    form.durationMinutes = String(draft.maxDurationMinutes);
  return form;
}

export function formatMinor(minor: number): string {
  return minor % 100 === 0 ? String(minor / 100) : (minor / 100).toFixed(2);
}

export function formatMoney(minor: number, currency: string): string {
  if (minor === 0) return "Free";
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
      minor / 100,
    );
  } catch {
    return `${formatMinor(minor)} ${currency}`;
  }
}

export type FieldErrors = Partial<Record<IntentField, string>>;

export type BuildResult =
  | { ok: true; submission: ConfirmedIntentSubmission }
  | { ok: false; errors: FieldErrors };

/**
 * Converts the confirmed form into the wire payload. Never fills a missing
 * required value with a default: blank fields are errors the person resolves.
 */
export function buildSubmission(
  form: IntentForm,
  community: OnboardingCommunity,
  context: { timeZone: string; expectedVersion: number; now: number },
): BuildResult {
  const errors: FieldErrors = {};
  const goal = form.goal.trim();
  if (!goal) errors.goal = "Describe what you'd enjoy doing.";
  else if (goal.length > LIMITS.goalChars)
    errors.goal = `Keep this under ${LIMITS.goalChars} characters.`;

  const interests = [...new Set(form.interests.map((i) => i.trim()).filter(Boolean))];
  if (!interests.length) errors.interests = "Add at least one interest.";
  else if (interests.length > LIMITS.interests)
    errors.interests = `Use at most ${LIMITS.interests} interests.`;
  else if (interests.some((i) => i.length > LIMITS.interestChars))
    errors.interests = `Each interest must be under ${LIMITS.interestChars} characters.`;

  if (!community.areas.some((a) => a.areaId === form.areaId))
    errors.areaId = "Choose where you can meet.";

  const availability: Window[] = [];
  if (!form.availability.length)
    errors.availability = "Add at least one time you're free.";
  else if (form.availability.length > LIMITS.windows)
    errors.availability = `Use at most ${LIMITS.windows} time windows.`;
  else {
    for (const w of form.availability) {
      const start = new Date(`${w.date}T${w.start}`);
      const end = new Date(`${w.date}T${w.end}`);
      if (!w.date || !w.start || !w.end || Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
        errors.availability = "Complete the date, start and end for every window.";
        break;
      }
      if (start >= end) {
        errors.availability = "Each window must end after it starts (same day).";
        break;
      }
      if (end.getTime() <= context.now) {
        errors.availability = "Time windows must be in the future.";
        break;
      }
      availability.push({ start: start.toISOString(), end: end.toISOString() });
    }
    availability.sort((a, b) => a.start.localeCompare(b.start));
    for (let i = 1; i < availability.length && !errors.availability; i++)
      if (availability[i].start < availability[i - 1].end)
        errors.availability = "Time windows overlap. Merge or adjust them.";
  }

  const budgetText = form.budget.trim();
  let maxBudgetMinor = -1;
  if (!budgetText) errors.maxBudgetMinor = "Enter a budget. Use 0 for free activities.";
  else if (!/^\d+(\.\d{1,2})?$/.test(budgetText))
    errors.maxBudgetMinor = "Enter an amount like 0, 10 or 7.50.";
  else {
    maxBudgetMinor = Math.round(Number(budgetText) * 100);
    if (maxBudgetMinor > LIMITS.maxBudgetMinor)
      errors.maxBudgetMinor = `Budget must be at most ${formatMinor(LIMITS.maxBudgetMinor)}.`;
  }

  const durationText = form.durationMinutes.trim();
  const maxDurationMinutes = Number(durationText);
  if (!durationText) errors.maxDurationMinutes = "Choose how long you can spend.";
  else if (
    !/^\d+$/.test(durationText) ||
    maxDurationMinutes < LIMITS.minDurationMinutes ||
    maxDurationMinutes > LIMITS.maxDurationMinutes
  )
    errors.maxDurationMinutes = `Enter ${LIMITS.minDurationMinutes}–${LIMITS.maxDurationMinutes} minutes.`;
  else if (
    !errors.availability &&
    !availability.some(
      (w) => Date.parse(w.end) - Date.parse(w.start) >= LIMITS.minDurationMinutes * 60_000,
    )
  )
    errors.availability = `At least one window must be ${LIMITS.minDurationMinutes} minutes or longer.`;

  if (Object.keys(errors).length) return { ok: false, errors };
  return {
    ok: true,
    submission: {
      communityId: community.communityId,
      goal,
      interests,
      areaId: form.areaId,
      timeZone: context.timeZone,
      availability,
      maxBudgetMinor,
      currency: community.currency,
      maxDurationMinutes,
      groupPreference: "small",
      expectedVersion: context.expectedVersion,
    },
  };
}
