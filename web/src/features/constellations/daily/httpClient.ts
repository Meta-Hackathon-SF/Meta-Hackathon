/*
 * Live client for the routes in contracts/API.md ("Weekly cycle", "Operator").
 * Used only when VITE_CONSTELLATIONS_API is set. The session is the server's
 * cookie (Patrik); this client never sends a playerId or a weight.
 */
import { createNudgeRequester } from "../nudges";
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
  parseFormationResponse,
  parseList,
  parseReport,
  parseTopUp,
  parseTranscript,
  type CycleClient,
} from "./client";
import { parseDailyConstellations, parseProposal, parseWeekView } from "./v3";
import { toWav } from "./wav";

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
    submit: (id, body) => mutate(call("POST", `${c(id)}/answers`, parseAnswerResult, { body })),
    edit: (id, day, body) => mutate(call("PATCH", `${c(id)}/answers/${day}`, parseAnswerResult, { body })),
    remove: (id, day) =>
      mutate(call("DELETE", `${c(id)}/answers/${day}`, () => undefined, { emptyOk: true })),
    followUp: (id, day, signal) => call("GET", `${c(id)}/answers/${day}/followup`, parseFollowUp, { signal }),
    async transcribe(audio, signal) {
      // The speech-to-text provider takes WAV only; convert in memory first.
      let wav: Blob;
      try {
        wav = await toWav(audio);
      } catch {
        throw new ClientError("INVALID_INPUT", "That recording could not be prepared.");
      }
      return call("POST", "/voice/transcribe", parseTranscript, { raw: wav, signal });
    },
    liveTranscriptionUrl() {
      // Same origin as the API (the session cookie rides along); ws:// or wss://.
      const url = new URL(`${base}/voice/live`, window.location.href);
      url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
      return url.toString();
    },
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
    async formationDebug(id, signal) {
      try {
        return await call("GET", `${op(id)}/formation-debug`, parseFormationResponse, { signal });
      } catch (error) {
        if (error instanceof ClientError && error.code === "NOT_FOUND") return null;
        throw error;
      }
    },
    async myRoomId(id, signal) {
      try {
        return await call("GET", `${c(id)}/room`, (v) => {
          const room = (v as { room?: { roomId?: unknown }; roomId?: unknown } | null) ?? {};
          const roomId = room.room?.roomId ?? room.roomId;
          return typeof roomId === "string" && roomId.length > 0 && roomId.length <= 128
            ? roomId
            : (() => {
                throw new ClientError("PROVIDER_UNAVAILABLE", "The server sent an unexpected response.", true);
              })();
        }, { signal });
      } catch (error) {
        if (error instanceof ClientError && (error.code === "NOT_FOUND" || error.code === "FORBIDDEN")) return null;
        throw error;
      }
    },
    nudge: createNudgeRequester(base),
    // PROPOSED routes from docs/PRD-v3.md (contract 3.0.0, D012). Until the producers
    // mount them these calls fail and the UI shows its pending/unavailable state.
    v3: {
      dailyConstellations: (id, day, signal) =>
        call("GET", `${c(id)}/days/${day}/constellations`, parseDailyConstellations, { signal }),
      week: (id, signal) => call("GET", `${c(id)}/week`, parseWeekView, { signal }),
      closeDay: (id, day) =>
        mutate(
          call("POST", `${op(id)}/close-day`, (v) => {
            const jobId = (v as { jobId?: unknown } | null)?.jobId;
            if (typeof jobId !== "string" || !jobId)
              throw new ClientError("PROVIDER_UNAVAILABLE", "The server sent an unexpected response.", true);
            return { jobId };
          }, { body: { day } }),
        ),
      customEvents: (signal) =>
        call("GET", "/operator/custom-events", (v) => parseList(v, (x) => parseProposal(x, parseEvidence)), { signal }),
      decideCustomEvent: (proposalId, decision, note) =>
        call(
          "POST",
          `/operator/custom-events/${encodeURIComponent(proposalId)}/decision`,
          (v) => parseProposal(v, parseEvidence),
          { body: note ? { decision, note } : { decision } },
        ),
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
