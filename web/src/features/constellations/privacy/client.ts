import { apiBase } from "../apiBase";
/*
 * Privacy client for the "Session, consent, safety" routes (contracts/API.md;
 * owner: Patrik). Wire types come from contracts/protocol.ts (type-only import).
 * TypeScript types are not validation, so every response is parsed at runtime.
 *
 * Live mode needs VITE_CONSTELLATIONS_API (same switch as the daily page). The
 * session is the server's HttpOnly cookie; this client never sends a playerId.
 * Without the env var, a labeled in-memory FIXTURE client is used: it provides
 * no authentication and every screen shows "Fixture mode".
 */
import type { Consent, ErrorCode, Player } from "../../../../../contracts/protocol.ts";
import { deriveTopics } from "./topics";

export interface ConsentToggles {
  matchAnswers: boolean;
  anonymousChat: boolean;
  isAdult: boolean;
}

/** Response of POST /communities/:id/join and GET /session (docs/DECISIONS.md D007). */
export interface SessionView {
  player: Player;
  consent: Consent;
  isOperator: boolean;
}

export class PrivacyError extends Error {
  readonly code: ErrorCode | "NETWORK" | "BAD_RESPONSE";
  readonly retryable: boolean;
  constructor(code: PrivacyError["code"], message: string, retryable = false) {
    super(message);
    this.code = code;
    this.retryable = retryable;
  }
}

/** D010: what the page collects for "use my activity". Texts never leave as text in fixture mode. */
export interface ActivityInput {
  profileId: string | null;
  groupIds: string[];
  eventIds: string[];
  friendIds: string[];
  texts: string[];
}
export interface ActivityResult {
  useActivity: boolean;
  topics: string[];
}
/** Fixture only: the stored signals (no text), so the fixture cycle can compute brightness. */
export interface FixtureActivity {
  profileId: string | null;
  groupIds: string[];
  eventIds: string[];
  friendIds: string[];
  topics: string[];
}
const ACTIVITY_KEY = "cst-activity-fixture";
export function readFixtureActivity(): FixtureActivity | null {
  try {
    const raw = sessionStorage.getItem(ACTIVITY_KEY);
    return raw ? (JSON.parse(raw) as FixtureActivity) : null;
  } catch {
    return null;
  }
}
function writeFixtureActivity(value: FixtureActivity | null) {
  try {
    if (value) sessionStorage.setItem(ACTIVITY_KEY, JSON.stringify(value));
    else sessionStorage.removeItem(ACTIVITY_KEY);
  } catch {
    /* storage blocked: the demo just has no activity signals */
  }
  try {
    window.dispatchEvent(new Event(ACTIVITY_EVENT));
  } catch {
    /* no window (tests) */
  }
}
/** Fired after the fixture activity changes, so pages can recompute. */
export const ACTIVITY_EVENT = "cst-activity-changed";

export interface PrivacyClient {
  readonly mode: "live" | "fixture";
  /** null when there is no session for this Group (not joined, expired, signed out). */
  session(communityId: string, signal?: AbortSignal): Promise<SessionView | null>;
  join(communityId: string, displayName: string, toggles: ConsentToggles): Promise<SessionView>;
  hostLogin(password: string): Promise<SessionView>;
  updateConsent(expectedVersion: number, toggles: ConsentToggles): Promise<Consent>;
  signOut(): Promise<void>;
  deleteMyData(): Promise<void>;
  /** D010: turn "use my activity" on (with the collected signals) or off (deletes them). */
  setActivity(useActivity: boolean, input?: ActivityInput): Promise<ActivityResult>;
}

export const allOn = (t: ConsentToggles): boolean => t.matchAnswers && t.anonymousChat && t.isAdult;

// ---------------------------------------------------------------- validators
function fail(): never {
  throw new PrivacyError("BAD_RESPONSE", "Unexpected response from the server.", true);
}
const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown): string => (typeof v === "string" && v.length > 0 ? v : fail());
const bool = (v: unknown): boolean => (typeof v === "boolean" ? v : fail());

export function parsePlayer(v: unknown): Player {
  if (!isObj(v)) fail();
  return {
    playerId: str(v.playerId),
    displayName: str(v.displayName),
    avatarColor: /^#[0-9a-f]{6}$/i.test(String(v.avatarColor)) ? String(v.avatarColor) : fail(),
    isSynthetic: bool(v.isSynthetic),
  };
}

export function parseConsent(v: unknown): Consent {
  if (!isObj(v)) fail();
  const version = Number.isInteger(v.version) && (v.version as number) >= 1 ? (v.version as number) : fail();
  const revokedAt = v.revokedAt === null ? null : str(v.revokedAt);
  return {
    playerId: str(v.playerId),
    communityId: str(v.communityId),
    matchAnswers: bool(v.matchAnswers),
    anonymousChat: bool(v.anonymousChat),
    isAdult: bool(v.isAdult),
    version,
    revokedAt,
    useActivity: v.useActivity === undefined ? false : bool(v.useActivity),
  };
}

export function parseSession(v: unknown): SessionView {
  if (!isObj(v)) fail();
  return { player: parsePlayer(v.player), consent: parseConsent(v.consent), isOperator: bool(v.isOperator) };
}

const CODES: ReadonlySet<string> = new Set([
  "INVALID_INPUT", "UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND", "CONSENT_REQUIRED", "STALE_REVISION",
  "PROVIDER_UNAVAILABLE", "RATE_LIMITED", "IDEMPOTENCY_CONFLICT", "CYCLE_LOCKED", "ROOM_EXPIRED", "MESSAGE_REJECTED",
]);

function parseError(body: unknown, status: number): PrivacyError {
  const e = isObj(body) && isObj(body.error) ? body.error : null;
  const code = e && typeof e.code === "string" && CODES.has(e.code) ? (e.code as ErrorCode) : "PROVIDER_UNAVAILABLE";
  const message = e && typeof e.message === "string" ? e.message : "Something went wrong.";
  const retryable = e && typeof e.retryable === "boolean" ? e.retryable : status >= 500;
  return new PrivacyError(code, message, retryable);
}

// ---------------------------------------------------------------- live client
export function httpPrivacyClient(base: string): PrivacyClient {
  async function call(path: string, init: RequestInit = {}): Promise<unknown> {
    const method = (init.method ?? "GET").toUpperCase();
    let res: Response;
    try {
      res = await fetch(base + path, {
        ...init,
        credentials: "include",
        headers: {
          Accept: "application/json",
          ...(init.body ? { "Content-Type": "application/json" } : {}),
          ...(method !== "GET" ? { "Idempotency-Key": crypto.randomUUID() } : {}),
        },
      });
    } catch (error) {
      if ((error as Error).name === "AbortError") throw error;
      throw new PrivacyError("NETWORK", "Can't reach Facebook Space right now.", true);
    }
    if (res.status === 204 || res.status === 202) return null;
    const body: unknown = await res.json().catch(() => null);
    if (!res.ok) throw parseError(body, res.status);
    return body;
  }

  return {
    mode: "live",
    async session(communityId, signal) {
      try {
        const view = parseSession(await call("/session", { signal }));
        return view.consent.communityId === communityId ? view : null; // sessions are Group-scoped
      } catch (error) {
        if (error instanceof PrivacyError && error.code === "UNAUTHENTICATED") return null;
        throw error;
      }
    },
    async join(communityId, displayName, toggles) {
      const body = JSON.stringify({ displayName, ...toggles });
      return parseSession(await call(`/communities/${encodeURIComponent(communityId)}/join`, { method: "POST", body }));
    },
    async hostLogin(password) {
      return parseSession(await call("/operator/login", { method: "POST", body: JSON.stringify({ password }) }));
    },
    async updateConsent(expectedVersion, toggles) {
      const body = JSON.stringify({ expectedVersion, ...toggles });
      return parseConsent(await call("/me/consent", { method: "PATCH", body }));
    },
    async signOut() {
      await call("/session", { method: "DELETE" });
    },
    async deleteMyData() {
      await call("/me/data", { method: "DELETE" });
    },
    async setActivity(useActivity, input) {
      const body = JSON.stringify(useActivity && input ? { useActivity, ...input } : { useActivity });
      const v = await call("/me/activity", { method: "PUT", body });
      if (!isObj(v) || !Array.isArray(v.topics)) fail();
      return { useActivity: bool(v.useActivity), topics: (v.topics as unknown[]).map(str) };
    },
  };
}

// ------------------------------------------------------------- fixture client
/**
 * FIXTURE client: one synthetic player per tab (sessionStorage, like the daily
 * page's fixture), UI development only. No authentication. Mirrors the server
 * rules: join needs all three toggles, consent updates are version-checked,
 * withdrawing sets revokedAt. Storage failures fall back to memory.
 */
const FIXTURE_KEY = "cst-privacy-fixture";

export function fixturePrivacyClient(): PrivacyClient {
  let memory: SessionView | null = null;
  const read = (): SessionView | null => {
    try {
      const raw = sessionStorage.getItem(FIXTURE_KEY);
      return raw ? parseSession(JSON.parse(raw)) : memory;
    } catch {
      return memory;
    }
  };
  const write = (next: SessionView | null) => {
    memory = next;
    try {
      if (next) sessionStorage.setItem(FIXTURE_KEY, JSON.stringify(next));
      else sessionStorage.removeItem(FIXTURE_KEY);
    } catch {
      /* private mode or blocked storage: memory only */
    }
  };
  let view: SessionView | null = read();
  const save = (next: SessionView | null) => {
    view = next;
    write(next);
  };
  const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  return {
    mode: "fixture",
    async session(communityId) {
      return view && view.consent.communityId === communityId ? view : null;
    },
    async join(communityId, displayName, toggles) {
      if (!allOn(toggles)) throw new PrivacyError("CONSENT_REQUIRED", "All three consents are required to play.");
      const name = displayName.trim();
      if (!name || name.length > 40) throw new PrivacyError("INVALID_INPUT", "Invalid fields: displayName");
      if (view && view.consent.communityId === communityId) return view;
      save({
        player: { playerId: "p_fixture", displayName: name, avatarColor: "#7c9cff", isSynthetic: false },
        consent: { playerId: "p_fixture", communityId, ...toggles, version: 1, revokedAt: null },
        isOperator: false,
      });
      return view!;
    },
    async hostLogin() {
      throw new PrivacyError("PROVIDER_UNAVAILABLE", "Host login requires the live server.");
    },
    async updateConsent(expectedVersion, toggles) {
      if (!view) throw new PrivacyError("UNAUTHENTICATED", "Join Facebook Space to continue.");
      const c = view.consent;
      if (c.version !== expectedVersion) {
        throw new PrivacyError("STALE_REVISION", "This was changed elsewhere. Reload and try again.");
      }
      const withdrawn = (["matchAnswers", "anonymousChat", "isAdult"] as const).some((k) => c[k] && !toggles[k]);
      const revokedAt = allOn(toggles) ? null : withdrawn ? now() : c.revokedAt;
      save({ ...view, consent: { ...c, ...toggles, version: c.version + 1, revokedAt } });
      return view!.consent;
    },
    async signOut() {
      save(null);
    },
    async deleteMyData() {
      if (!view) throw new PrivacyError("UNAUTHENTICATED", "Join Facebook Space to continue.");
      writeFixtureActivity(null);
      save({ ...view, consent: { ...view.consent, useActivity: false } });
    },
    async setActivity(useActivity, input) {
      if (!view) throw new PrivacyError("UNAUTHENTICATED", "Join Facebook Space to continue.");
      if (useActivity && !allOn(view.consent)) throw new PrivacyError("CONSENT_REQUIRED", "Turn the three switches on first.");
      if (!useActivity || !input) {
        writeFixtureActivity(null);
        save({ ...view, consent: { ...view.consent, useActivity: false } });
        return { useActivity: false, topics: [] };
      }
      const topics = deriveTopics(input.texts); // texts are dropped here, like the server
      writeFixtureActivity({
        profileId: input.profileId,
        groupIds: [...new Set(input.groupIds)].sort(),
        eventIds: [...new Set(input.eventIds)].sort(),
        friendIds: [...new Set(input.friendIds)].sort(),
        topics,
      });
      save({ ...view, consent: { ...view.consent, useActivity: true } });
      return { useActivity: true, topics };
    },
  };
}

let shared: PrivacyClient | null = null;

/** One client per page load, chosen like the daily page's client. */
export function getPrivacyClient(): PrivacyClient {
  if (!shared) {
    const base = apiBase();
    shared = base ? httpPrivacyClient(base) : fixturePrivacyClient();
  }
  return shared;
}
