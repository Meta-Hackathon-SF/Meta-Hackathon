/**
 * Live adapter for the routes in contracts/API.md. Session identity comes from
 * the server-verified cookie (credentials: "include"); no participantId is sent.
 * Not yet exercised against a running server: Kai/Patrik/Adam endpoints are
 * pending. See docs/handoffs/will.md.
 */
import type { ErrorCode, Mode } from "../../../../../contracts/protocol";
import { OnboardingError, type OnboardingPorts } from "./types";
import { parseExtraction, parsePrivateIntent } from "./validation";

const ERROR_CODES: readonly ErrorCode[] = [
  "INVALID_INPUT",
  "UNAUTHENTICATED",
  "FORBIDDEN",
  "NOT_FOUND",
  "CONSENT_REQUIRED",
  "STALE_REVISION",
  "CAPACITY_REACHED",
  "PROVIDER_UNAVAILABLE",
  "RATE_LIMITED",
  "IDEMPOTENCY_CONFLICT",
];

async function toError(response: Response): Promise<OnboardingError> {
  const requestId = response.headers.get("X-Request-Id");
  try {
    const body: unknown = await response.json();
    const error = (body as { error?: Record<string, unknown> })?.error;
    if (
      error &&
      ERROR_CODES.includes(error.code as ErrorCode) &&
      typeof error.message === "string" &&
      typeof error.retryable === "boolean"
    )
      return new OnboardingError(
        error.code as ErrorCode,
        error.message,
        error.retryable,
        typeof error.requestId === "string" ? error.requestId : requestId,
      );
  } catch {
    // Fall through to a generic error; never surface raw bodies.
  }
  return new OnboardingError(
    "INVALID_RESPONSE",
    `Unexpected server response (${response.status}).`,
    response.status >= 500,
    requestId,
  );
}

export function createHttpOnboardingPorts(baseUrl: string, mode: Mode): OnboardingPorts {
  const root = baseUrl.replace(/\/+$/, "") + "/api/v1";

  async function send(path: string, init: RequestInit): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(root + path, { credentials: "include", ...init });
    } catch (error) {
      if ((error as Error).name === "AbortError") throw error;
      throw new OnboardingError("NETWORK", "Could not reach the server.", true);
    }
    if (response.status === 202)
      // Async job polling (GET /jobs/:id) is not wired for onboarding yet.
      throw new OnboardingError(
        "INVALID_RESPONSE",
        "The server queued this request; async onboarding jobs are not supported yet.",
        false,
        response.headers.get("X-Request-Id"),
      );
    if (!response.ok) throw await toError(response);
    try {
      return await response.json();
    } catch {
      throw new OnboardingError("INVALID_RESPONSE", "Server returned invalid JSON.", false);
    }
  }

  return {
    mode,
    async transcribe(audio, signal) {
      const body = new FormData();
      body.append("audio", audio, "intent-recording");
      const result = await send("/voice/transcribe", {
        method: "POST",
        body,
        signal,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      const transcript = (result as { transcript?: unknown })?.transcript;
      if (typeof transcript !== "string")
        throw new OnboardingError("INVALID_RESPONSE", "Transcription response is malformed.", false);
      return { transcript };
    },
    async extract({ transcript, communityId }, signal) {
      const result = await send("/intents/extract", {
        method: "POST",
        signal,
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({ transcript, communityId }),
      });
      return parseExtraction(result);
    },
    async confirm(submission, { signal, idempotencyKey }) {
      const result = await send("/intents/me", {
        method: "PUT",
        signal,
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify(submission),
      });
      return parsePrivateIntent(result);
    },
  };
}
