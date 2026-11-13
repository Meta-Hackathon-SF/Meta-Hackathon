/*
 * Operator reasoning trace (owner: Will UI; route by Adam: GET /operator/reasoning,
 * PROPOSED, not yet in contracts/API.md). Codes and counts only: the server never
 * sends prompts, outputs or player data, and this validator drops anything else.
 */
import { ClientError } from "../daily/client";

export interface ReasoningCheck {
  stage: string;
  code: string;
  count: number;
}
export interface ReasoningEntry {
  requestId: string;
  at: string;
  task: string | null;
  callType: string | null;
  model: string | null;
  source: string | null;
  outcome: string | null;
  attempts: number | null;
  latencyMs: number | null;
  checks: ReasoningCheck[];
}

const CODE = /^[a-z][a-z0-9_]{0,39}$/;
const SHORT = /^[A-Za-z0-9_.:\- ]{1,120}$/;
const bad = (): never => {
  throw new ClientError("PROVIDER_UNAVAILABLE", "The server sent an unexpected response.", true);
};
const opt = (v: unknown, re: RegExp): string | null => (v === undefined || v === null ? null : typeof v === "string" && re.test(v) ? v : bad());
const optNum = (v: unknown): number | null =>
  v === undefined || v === null ? null : typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : bad();

export function parseReasoning(v: unknown): ReasoningEntry[] {
  if (!Array.isArray(v) || v.length > 300) return bad();
  return v.map((item) => {
    if (typeof item !== "object" || item === null) return bad();
    const o = item as Record<string, unknown>;
    const checks = Array.isArray(o.checks) ? o.checks : bad();
    return {
      requestId: opt(o.requestId, SHORT) ?? bad(),
      at: opt(o.at, SHORT) ?? bad(),
      task: opt(o.task, CODE),
      callType: opt(o.callType, SHORT),
      model: opt(o.model, SHORT),
      source: opt(o.source, CODE),
      outcome: opt(o.outcome, CODE),
      attempts: optNum(o.attempts),
      latencyMs: optNum(o.latencyMs),
      checks: checks.slice(0, 40).map((c) => {
        const r = (typeof c === "object" && c !== null ? c : bad()) as Record<string, unknown>;
        return { stage: opt(r.stage, CODE) ?? bad(), code: opt(r.code, CODE) ?? bad(), count: optNum(r.count) ?? 0 };
      }),
    };
  });
}
