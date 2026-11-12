/**
 * TEST/DEVELOPMENT DOUBLE. Not Muse, not speech-to-text, not persistence.
 * - transcribe() ignores the audio entirely and returns a canned sentence, so
 *   no recording leaves the browser.
 * - extract() uses keyword rules, not model reasoning, and never guesses
 *   availability.
 * - confirm() echoes the payload with fixture identifiers, in memory only.
 * The UI labels every result from this adapter as fixture data.
 */
import type { PrivateIntent } from "../../../../../contracts/protocol";
import {
  OnboardingError,
  type IntentDraft,
  type IntentExtraction,
  type IntentField,
  type OnboardingCommunity,
  type OnboardingPorts,
} from "./types";
import { parseExtraction, parsePrivateIntent } from "./validation";

export const FIXTURE_TRANSCRIPT =
  "I'd love to do a short photo walk with a few people near the main quad. " +
  "Something free or under $10, about an hour.";

export interface FixtureOptions {
  /** Artificial latency per call, for exercising cancellation. */
  delayMs?: number;
  /** Force a retryable provider failure for one operation. */
  fail?: "transcribe" | "extract" | "confirm" | null;
  community: OnboardingCommunity;
}

const KEYWORDS: [RegExp, string][] = [
  [/\bphoto|camera|picture/i, "photography"],
  [/\bwalk|hike|stroll/i, "walking"],
  [/\bcoffee|caf[eé]/i, "coffee"],
  [/\bboard ?games?|chess/i, "board games"],
  [/\bclimb/i, "climbing"],
  [/\brun(ning)?\b|\bjog/i, "running"],
  [/\bmusic|jam|guitar|sing/i, "music"],
  [/\bcod(e|ing)|hack/i, "coding"],
  [/\bart\b|draw|sketch|paint/i, "art"],
  [/\bfood|lunch|dinner|cook|eat\b/i, "food"],
  [/\bbasketball|soccer|volleyball|frisbee/i, "sports"],
];

function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const timer = setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });
}

export function fixtureExtract(
  transcript: string,
  community: OnboardingCommunity,
): IntentExtraction {
  const text = transcript.trim();
  const draft: IntentDraft = {};
  const firstSentence = text.split(/(?<=[.!?])\s/)[0]?.trim();
  if (firstSentence) draft.goal = firstSentence.slice(0, 300);

  const interests = KEYWORDS.filter(([re]) => re.test(text)).map(([, tag]) => tag);
  if (interests.length) draft.interests = interests;

  const area = community.areas.find((a) =>
    text.toLowerCase().includes(a.name.toLowerCase()),
  );
  if (area) draft.areaId = area.areaId;

  const money = text.match(/\$\s?(\d+(?:\.\d{1,2})?)/);
  if (money) {
    draft.maxBudgetMinor = Math.round(Number(money[1]) * 100);
    draft.currency = community.currency;
  } else if (/\bfree\b/i.test(text)) {
    draft.maxBudgetMinor = 0;
    draft.currency = community.currency;
  }

  const minutes = text.match(/(\d+)\s*(?:min|mins|minutes)\b/i);
  const hours = text.match(/(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hours?)\b/i);
  if (minutes) draft.maxDurationMinutes = Number(minutes[1]);
  else if (hours) draft.maxDurationMinutes = Math.round(Number(hours[1]) * 60);
  else if (/\b(an|one) hour\b/i.test(text)) draft.maxDurationMinutes = 60;
  else if (/\bhalf an hour\b/i.test(text)) draft.maxDurationMinutes = 30;

  // Availability is never inferred by the fixture; the person always adds it.
  const required: [IntentField, boolean][] = [
    ["goal", !!draft.goal],
    ["interests", !!draft.interests],
    ["areaId", !!draft.areaId],
    ["availability", false],
    ["maxBudgetMinor", draft.maxBudgetMinor !== undefined],
    ["maxDurationMinutes", draft.maxDurationMinutes !== undefined],
  ];
  return parseExtraction({
    draft,
    missingFields: required.filter(([, ok]) => !ok).map(([f]) => f),
    evidence: null,
  });
}

export function createFixtureOnboardingPorts(options: FixtureOptions): OnboardingPorts {
  const wait = options.delayMs ?? 500;
  const failIf = (op: FixtureOptions["fail"]) => {
    if (options.fail === op)
      throw new OnboardingError(
        "PROVIDER_UNAVAILABLE",
        "Fixture provider failure (simulated).",
        true,
        "fixture-request",
      );
  };
  return {
    mode: "fixture",
    async transcribe(_audio, signal) {
      await delay(wait, signal);
      failIf("transcribe");
      return { transcript: FIXTURE_TRANSCRIPT };
    },
    async extract({ transcript }, signal) {
      await delay(wait, signal);
      failIf("extract");
      return fixtureExtract(transcript, options.community);
    },
    async confirm(submission, { signal }) {
      await delay(wait, signal);
      failIf("confirm");
      const { expectedVersion, ...fields } = submission;
      const intent: PrivateIntent = {
        ...fields,
        participantId: "fixture-participant",
        intentVersion: expectedVersion + 1,
        consentVersion: 1,
        confirmedAt: new Date().toISOString(),
      };
      return parsePrivateIntent(intent);
    },
  };
}
