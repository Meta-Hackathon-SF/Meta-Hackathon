import type { ApiError, ExtractionResult, IntentField, ModelEvidence } from "./types";

const INTENT_FIELDS: readonly IntentField[] = [
  "goal",
  "interests",
  "areaId",
  "availability",
  "maxBudgetMinor",
  "maxDurationMinutes",
];

export class PlanningApiError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly requestId: string | null;
  constructor(code: string, message: string, retryable: boolean, requestId: string | null) {
    super(message);
    this.code = code;
    this.retryable = retryable;
    this.requestId = requestId;
  }
}

type Json = Record<string, unknown>;
const isObj = (v: unknown): v is Json => typeof v === "object" && v !== null && !Array.isArray(v);
const isStr = (v: unknown, max = 600): v is string => typeof v === "string" && v.length <= max;
const isInt = (v: unknown): v is number => Number.isInteger(v) && (v as number) >= 0;
const isTime = (v: unknown) => isStr(v, 40) && /Z$/.test(v) && !Number.isNaN(Date.parse(v));

function fail(path: string): never {
  throw new PlanningApiError("INVALID_RESPONSE", `Unexpected server response at ${path}`, true, null);
}

export function parseEvidence(v: unknown, path = "evidence"): ModelEvidence {
  if (!isObj(v) || !isStr(v.model, 100) || (v.source !== "live" && v.source !== "replay") || !isTime(v.generatedAt) || !isInt(v.latencyMs)) {
    fail(path);
  }
  return { model: v.model, source: v.source, generatedAt: v.generatedAt as string, latencyMs: v.latencyMs };
}

/** Runtime validation of the PROPOSED (D005) ExtractionResult. */
export function parseExtractionResult(v: unknown): ExtractionResult {
  if (!isObj(v) || v.status !== "draft" || !isObj(v.draft)) fail("$");
  const d = v.draft;
  const nullableStr = (x: unknown, max: number) => x === null || isStr(x, max);
  const nullableInt = (x: unknown) => x === null || isInt(x);
  if (
    !isStr(d.communityId, 128) ||
    !nullableStr(d.goal, 280) ||
    !Array.isArray(d.interests) ||
    !d.interests.every((i) => isStr(i, 40)) ||
    !nullableStr(d.areaId, 128) ||
    !isStr(d.timeZone, 64) ||
    !Array.isArray(d.availability) ||
    !d.availability.every((w) => isObj(w) && isTime(w.start) && isTime(w.end) && Date.parse(w.start as string) < Date.parse(w.end as string)) ||
    !nullableInt(d.maxBudgetMinor) ||
    !isStr(d.currency, 3) ||
    !nullableInt(d.maxDurationMinutes) ||
    d.groupPreference !== "small"
  ) {
    fail("draft");
  }
  if (!Array.isArray(v.missingFields) || !v.missingFields.every((f) => INTENT_FIELDS.includes(f as IntentField))) fail("missingFields");
  if (!Array.isArray(v.questions) || !v.questions.every((q) => isObj(q) && INTENT_FIELDS.includes(q.field as IntentField) && isStr(q.question, 200))) {
    fail("questions");
  }
  parseEvidence(v.evidence);
  return v as unknown as ExtractionResult;
}

async function readError(res: Response): Promise<PlanningApiError> {
  const requestId = res.headers.get("X-Request-Id");
  try {
    const body = (await res.json()) as ApiError;
    if (isObj(body) && isObj(body.error) && isStr(body.error.code, 40) && isStr(body.error.message, 300)) {
      return new PlanningApiError(body.error.code, body.error.message, body.error.retryable === true, body.error.requestId ?? requestId);
    }
  } catch {
    /* fall through */
  }
  return new PlanningApiError("HTTP_" + res.status, "The server could not complete the request.", res.status >= 500, requestId);
}

export interface ExtractIntentOptions {
  baseUrl: string; // e.g. "/api/v1" (public setting only)
  transcript: string;
  communityId: string;
  signal?: AbortSignal;
  fetchImpl?: typeof fetch;
}

/** POST /intents/extract. Session comes from the server-verified cookie, never a client participantId. */
export async function extractIntent(opts: ExtractIntentOptions): Promise<ExtractionResult> {
  const f = opts.fetchImpl ?? fetch;
  const res = await f(`${opts.baseUrl}/intents/extract`, {
    method: "POST",
    credentials: "include",
    signal: opts.signal,
    headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ transcript: opts.transcript, communityId: opts.communityId }),
  });
  if (!res.ok) throw await readError(res);
  return parseExtractionResult(await res.json());
}

/**
 * Latest-request-wins guard: starting a new request aborts the previous one and
 * results from superseded requests are never delivered (contracts/API.md).
 */
export function createLatestOnly() {
  let seq = 0;
  let controller: AbortController | null = null;
  return async function run<T>(fn: (signal: AbortSignal) => Promise<T>): Promise<{ stale: false; value: T } | { stale: true }> {
    controller?.abort();
    const mine = ++seq;
    controller = new AbortController();
    try {
      const value = await fn(controller.signal);
      return mine === seq ? { stale: false, value } : { stale: true };
    } catch (err) {
      if (mine !== seq || (err instanceof DOMException && err.name === "AbortError")) return { stale: true };
      throw err;
    }
  };
}
