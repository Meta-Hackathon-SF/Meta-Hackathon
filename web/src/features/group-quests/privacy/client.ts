import type { ApiError, Consent, ErrorCode, PrivateIntent } from "../../../../../contracts/protocol";

/** Privacy-owned DTOs (docs/DECISIONS.md D007). Shared wire types come from contracts/protocol.ts. */
export interface ConsentToggles {
  matching: boolean;
  modelProcessing: boolean;
  publicInterests: boolean;
}
export interface MembershipView {
  communityId: string;
  displayName: string;
  consent: Consent;
  hasIntent: boolean;
  intentVersion: number | null;
}
export interface SessionView {
  participantId: string;
  expiresAt: string;
  memberships: MembershipView[];
}

export class PrivacyApiError extends Error {
  readonly code: ErrorCode | "NETWORK";
  readonly requestId: string | null;
  readonly retryable: boolean;
  constructor(code: ErrorCode | "NETWORK", message: string, requestId: string | null, retryable: boolean) {
    super(message);
    this.code = code;
    this.requestId = requestId;
    this.retryable = retryable;
  }
}

/** Port used by every privacy component. `mode` is shown in the UI. */
export interface PrivacyClient {
  readonly mode: "live" | "fixture";
  getSession(signal?: AbortSignal): Promise<SessionView | null>;
  startSession(): Promise<SessionView>;
  endSession(): Promise<void>;
  join(communityId: string, displayName: string, consent: ConsentToggles): Promise<MembershipView>;
  updateConsent(communityId: string, expectedVersion: number, consent: ConsentToggles): Promise<Consent>;
  leave(communityId: string): Promise<Consent>;
  getIntent(communityId: string, signal?: AbortSignal): Promise<PrivateIntent | null>;
}

const MUTATIONS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

async function call<T>(base: string, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  const method = (init.method ?? "GET").toUpperCase();
  try {
    response = await fetch(base + path, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        // Kai's server requires one key per mutation (contracts/API.md). Each user
        // action is a new key; privacy writes are also version-guarded (expectedVersion).
        ...(MUTATIONS.has(method) ? { "Idempotency-Key": crypto.randomUUID() } : {}),
      },
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new PrivacyApiError("NETWORK", "Can't reach Group Quests right now.", null, true);
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const err = (body as ApiError | null)?.error;
    throw new PrivacyApiError(
      err?.code ?? "PROVIDER_UNAVAILABLE",
      err?.message ?? "Something went wrong.",
      err?.requestId ?? response.headers.get("X-Request-Id"),
      err?.retryable ?? response.status >= 500,
    );
  }
  return body as T;
}

export function httpPrivacyClient(base = "/api/v1"): PrivacyClient {
  return {
    mode: "live",
    async getSession(signal) {
      try {
        return await call<SessionView>(base, "/session", { signal });
      } catch (error) {
        if (error instanceof PrivacyApiError && error.code === "UNAUTHENTICATED") return null;
        throw error;
      }
    },
    startSession: () => call(base, "/session", { method: "POST" }),
    endSession: () => call(base, "/session", { method: "DELETE" }),
    join: (communityId, displayName, consent) =>
      call(base, `/communities/${encodeURIComponent(communityId)}/join`, {
        method: "POST",
        body: JSON.stringify({ displayName, consent }),
      }),
    updateConsent: (communityId, expectedVersion, consent) =>
      call(base, `/communities/${encodeURIComponent(communityId)}/consent`, {
        method: "PATCH",
        body: JSON.stringify({ expectedVersion, ...consent }),
      }),
    leave: (communityId) =>
      call(base, `/communities/${encodeURIComponent(communityId)}/leave`, { method: "POST" }),
    async getIntent(communityId, signal) {
      try {
        return await call<PrivateIntent>(base, `/intents/me?communityId=${encodeURIComponent(communityId)}`, { signal });
      } catch (error) {
        if (error instanceof PrivacyApiError && error.code === "NOT_FOUND") return null;
        throw error;
      }
    },
  };
}

/**
 * FIXTURE client: in-memory, single synthetic participant, for UI development
 * before the server is reachable. Components show a "Fixture" badge. Never use
 * on a live path; it provides no authentication.
 */
export function fixturePrivacyClient(): PrivacyClient {
  let session: SessionView | null = null;
  const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const membership = (communityId: string) => {
    const found = session?.memberships.find((m) => m.communityId === communityId);
    if (!found) throw new PrivacyApiError("NOT_FOUND", "Not found.", "fixture", false);
    return found;
  };
  return {
    mode: "fixture",
    getSession: async () => session,
    startSession: async () => {
      session ??= { participantId: "p_fixture", expiresAt: now(), memberships: [] };
      return session;
    },
    endSession: async () => {
      session = null;
    },
    join: async (communityId, displayName, toggles) => {
      if (!session) throw new PrivacyApiError("UNAUTHENTICATED", "Sign in to continue.", "fixture", false);
      const existing = session.memberships.find((m) => m.communityId === communityId);
      if (existing) return existing;
      const view: MembershipView = {
        communityId,
        displayName,
        hasIntent: false,
        intentVersion: null,
        consent: { participantId: session.participantId, communityId, version: 1, ...toggles, revokedAt: null },
      };
      session.memberships.push(view);
      return view;
    },
    updateConsent: async (communityId, expectedVersion, toggles) => {
      const m = membership(communityId);
      if (m.consent.version !== expectedVersion) {
        throw new PrivacyApiError("STALE_REVISION", "This was changed elsewhere. Reload and try again.", "fixture", false);
      }
      const revoked = (Object.keys(toggles) as (keyof ConsentToggles)[]).some((k) => m.consent[k] && !toggles[k]);
      m.consent = { ...m.consent, ...toggles, version: expectedVersion + 1, revokedAt: revoked ? now() : null };
      return m.consent;
    },
    leave: async (communityId) => {
      const m = membership(communityId);
      session!.memberships = session!.memberships.filter((x) => x !== m);
      return { ...m.consent, matching: false, modelProcessing: false, publicInterests: false, version: m.consent.version + 1, revokedAt: now() };
    },
    getIntent: async () => null,
  };
}
