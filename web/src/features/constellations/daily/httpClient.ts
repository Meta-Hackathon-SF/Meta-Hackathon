/*
 * Live client for the routes in contracts/API.md ("Weekly cycle", "Operator").
 * Used only when VITE_CONSTELLATIONS_API is set. The session is the server's
 * cookie (Patrik); this client never sends a playerId or a weight.
 */
import {
  ClientError,
  parseAnswer,
  parseAnswerResult,
  parseApiError,
  parseCurrent,
  parseCycle,
  parseDailyQuestion,
  parseEvidence,
  parseFollowUp,
  parseGuess,
  parseList,
  parseReport,
  parseTopUp,
  parseTranscript,
  type CycleClient,
} from "./client";

function key(): string {
  return crypto.randomUUID();
}

export function createHttpClient(
  base: string,
  options: { isOperator: boolean; communityId: string },
): CycleClient {
  const listeners = new Set<() => void>();
  const changed = () => listeners.forEach((listener) => listener());

  async function call<T>(
    method: string,
    path: string,
    parse: (value: unknown) => T,
    init: { body?: unknown; raw?: Blob; signal?: AbortSignal; emptyOk?: boolean } = {},
  ): Promise<T> {
    const headers: Record<string, string> = {};
    if (method !== "GET") headers["Idempotency-Key"] = key();
    if (init.body !== undefined) headers["Content-Type"] = "application/json";
    if (init.raw) headers["Content-Type"] = init.raw.type || "audio/webm";
    let response: Response;
    try {
      response = await fetch(`${base}${path}`, {
        method,
        headers,
        credentials: "include",
        signal: init.signal,
        body: init.raw ?? (init.body === undefined ? undefined : JSON.stringify(init.body)),
      });
    } catch (error) {
      if ((error as Error)?.name === "AbortError") throw error;
      throw new ClientError("PROVIDER_UNAVAILABLE", "The server could not be reached.", true);
    }
    if (response.status === 204 && init.emptyOk) return undefined as T;
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new ClientError("PROVIDER_UNAVAILABLE", "The server sent an unexpected response.", true);
    }
    if (!response.ok) {
      const error = parseApiError(payload);
      throw new ClientError(error.code, error.message, error.retryable);
    }
    return parse(payload);
  }

  const c = (cycleId: string) => `/cycles/${encodeURIComponent(cycleId)}`;
  const op = (cycleId: string) => `/operator/cycles/${encodeURIComponent(cycleId)}`;
  const mutate = async <T,>(work: Promise<T>): Promise<T> => {
    const result = await work;
    changed();
    return result;
  };

  return {
    mode: "live",
    isOperator: options.isOperator,
    async current(signal) {
      try {
        return await call("GET", "/cycles/current", parseCurrent, { signal });
      } catch (error) {
        if (error instanceof ClientError && error.code === "NOT_FOUND") return null;
        throw error;
      }
    },
    questions: (id, signal) => call("GET", `${c(id)}/questions`, (v) => parseList(v, parseDailyQuestion), { signal }),
    myAnswers: (id, signal) => call("GET", `${c(id)}/answers`, (v) => parseList(v, parseAnswer), { signal }),
    // No read route for the guess exists in contracts/API.md; the slider starts unset.
    myGuess: async () => null,
    submit: (id, body) => mutate(call("POST", `${c(id)}/answers`, parseAnswerResult, { body })),
    edit: (id, day, body) => mutate(call("PATCH", `${c(id)}/answers/${day}`, parseAnswerResult, { body })),
    remove: (id, day) =>
      mutate(call("DELETE", `${c(id)}/answers/${day}`, () => undefined, { emptyOk: true })),
    followUp: (id, day, signal) => call("GET", `${c(id)}/answers/${day}/followup`, parseFollowUp, { signal }),
    guess: (id, percent) => call("PUT", `${c(id)}/guess`, parseGuess, { body: { percent } }),
    transcribe: (audio, signal) => call("POST", "/voice/transcribe", parseTranscript, { raw: audio, signal }),
    createCycle: () =>
      mutate(
        call("POST", "/operator/cycles", parseCycle, {
          body: { communityId: options.communityId, demoTiming: true },
        }),
      ),
    advance: (id) => mutate(call("POST", `${op(id)}/advance`, parseCycle, { body: {} })),
    topUp: (id) => mutate(call("POST", `${op(id)}/synthetic-topup`, parseTopUp)),
    reset: (id) => mutate(call("POST", `${op(id)}/reset`, parseCycle)),
    calls: (signal) => call("GET", "/operator/calls", (v) => parseList(v, parseEvidence), { signal }),
    reports: (signal) => call("GET", "/operator/reports", (v) => parseList(v, parseReport), { signal }),
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
