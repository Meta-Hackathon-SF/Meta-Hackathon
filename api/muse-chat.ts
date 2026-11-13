/**
 * POST /api/muse-chat: one short Muse line for the Sunday Messenger group.
 *
 * Runs as a Vercel Function on the deployed demo (repo-root api/, since the
 * Vercel project builds from the repo root; key from the MUSE_API_KEY env var)
 * and inside the Vite dev server (web/museChatPlugin.ts; key from the gitignored
 * server/providers/muse.env). Both read the same web/src/data/catalog.json.
 *
 * The browser sends only a task kind and the last few chat lines, with members
 * already renamed to "Member 1..." and "You". Facts come from the catalog, never
 * from the request. Muse may only point at catalog ids or propose an event draft
 * on an approved venue; ids and drafts are checked here and again in the browser
 * (museHelp.ts), which swaps in a labeled catalog reply if anything is off.
 */

import fs from "node:fs";
import path from "node:path";

type Kind = "hangout" | "supplies" | "barter" | "create";

/** The parts of web/src/data/catalog.json this route reads. */
export interface Catalog {
  venues: { placeId: string; name: string }[];
  items: { itemId: string; title: string; price: string; description: string }[];
  events: { eventId: string; title: string; placeId: string; when: string; description: string }[];
}

const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];

/** Ids Muse may point at, and the only facts it sees. */
function prepare(catalog: Catalog) {
  return {
    venueIds: new Set(catalog.venues.map((v) => v.placeId)),
    itemIds: new Set(catalog.items.map((i) => i.itemId)),
    eventIds: new Set(catalog.events.map((e) => e.eventId)),
    facts: {
      events: catalog.events.map((e) => ({
        eventId: e.eventId,
        title: e.title,
        venue: catalog.venues.find((v) => v.placeId === e.placeId)?.name,
        when: e.when,
        about: e.description,
      })),
      items: catalog.items.map((i) => ({ itemId: i.itemId, title: i.title, price: i.price, about: i.description })),
      venues: catalog.venues,
      vendor: { name: "Campus Cafe", ask: "a table for the group", offer: "bring the coffee set from Marketplace and split the check" },
    },
  };
}

let cached: Catalog | null = null;
/** Vercel: the function runs from the repo root and vercel.json ships the JSON with it (includeFiles). */
function loadCatalog(): Catalog {
  cached ??= JSON.parse(fs.readFileSync(path.join(process.cwd(), "web/src/data/catalog.json"), "utf8")) as Catalog;
  return cached;
}

const INSTRUCTIONS = [
  "You help a small group chat plan things. Reply to the latest note only, in one or two short sentences, no emoji. Earlier notes are context. Do not quote anyone.",
  "You never bring, buy, book, hold, reserve or register anything yourself. Never say I'll, I will, or let me. Never say anything is booked, held or confirmed.",
  "Use only the catalog facts. Point at catalog entries by id; the app shows them as cards, so do not list details the card already shows.",
  "task=hangout: pick 1 or 2 eventIds that best fit the chat. Mention the event title. Do not mention items.",
  "task=supplies: pick 1 or 2 itemIds that best fit the chat. Say they are demo listings, not purchases.",
  "task=barter: tell the group to ask Campus Cafe, and say nothing is booked until the cafe agrees. You may pick the coffee set itemId.",
  "task=create: propose one new event as draft {title (3-60 chars), placeId from venues, day (a weekday name), time (24h HH:MM between 08:00 and 22:00), description (under 160 chars)} from what the group wants. Say it is a draft they can create. Do not invent venues.",
].join(" ");

export interface MuseConfig {
  key: string;
  model: string;
}

export interface MuseDraft {
  title: string;
  placeId: string;
  day: string;
  time: string;
  description: string;
}

export interface MuseReply {
  text: string;
  source: "live";
  itemIds: string[];
  eventIds: string[];
  draft: MuseDraft | null;
}

export interface MuseResult {
  status: number;
  body: MuseReply | { error: string };
}

function ids(value: unknown, allowed: Set<string>): string[] {
  return Array.isArray(value) ? [...new Set(value.filter((v): v is string => typeof v === "string" && allowed.has(v)))].slice(0, 2) : [];
}

/** Server-side check; the browser checks again before showing a Create button. */
function cleanDraft(value: unknown, venueIds: Set<string>): MuseDraft | null {
  if (!value || typeof value !== "object") return null;
  const d = value as Record<string, unknown>;
  const str = (k: string, max: number) => (typeof d[k] === "string" ? (d[k] as string).trim().slice(0, max) : "");
  const draft = { title: str("title", 60), placeId: str("placeId", 40), day: str("day", 12), time: str("time", 5), description: str("description", 160) };
  const hour = /^([01]\d|2[0-3]):[0-5]\d$/.test(draft.time) ? Number(draft.time.slice(0, 2)) : -1;
  if (draft.title.length < 3 || !venueIds.has(draft.placeId) || !WEEKDAYS.includes(draft.day.toLowerCase()) || hour < 8 || hour > 22) return null;
  return draft;
}

// Best-effort limit per client (per server instance), so a public deploy can't be used as a free model proxy.
const WINDOW_MS = 60_000;
const MAX_PER_WINDOW = 12;
const hits = new Map<string, number[]>();
function limited(client: string): boolean {
  const now = Date.now();
  const recent = (hits.get(client) ?? []).filter((t) => now - t < WINDOW_MS);
  recent.push(now);
  hits.set(client, recent);
  if (hits.size > 5000) hits.clear();
  return recent.length > MAX_PER_WINDOW;
}

function isKind(value: unknown): value is Kind {
  return value === "hangout" || value === "supplies" || value === "barter" || value === "create";
}

function cleanContext(value: unknown): { sender: string; text: string }[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((note) => {
      if (!note || typeof note !== "object") return null;
      const n = note as { sender?: unknown; text?: unknown };
      const sender = typeof n.sender === "string" ? n.sender.slice(0, 20) : "";
      const text = typeof n.text === "string" ? n.text.trim().slice(0, 200) : "";
      // Only anonymous labels reach the model.
      if (!/^(You|Muse|Member [1-9])$/.test(sender) || !text) return null;
      return { sender, text };
    })
    .filter((note): note is { sender: string; text: string } => note !== null)
    .slice(-6);
}

/** Validates the request, calls Muse once, and returns a JSON response shape. Never echoes the request. */
export async function handleMuseChat(body: unknown, config: MuseConfig | null, catalog: Catalog, client = "local"): Promise<MuseResult> {
  const { venueIds, itemIds, eventIds, facts } = prepare(catalog);
  const record = body && typeof body === "object" ? (body as { kind?: unknown; context?: unknown }) : {};
  const kind = record.kind;
  const context = cleanContext(record.context);
  if (!isKind(kind) || context.length === 0) return { status: 400, body: { error: "needs a message" } };
  if (!config) return { status: 503, body: { error: "not_configured" } };
  if (limited(client)) return { status: 429, body: { error: "slow_down" } };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20_000);
  try {
    const response = await fetch("https://api.meta.ai/v1/chat/completions", {
      method: "POST",
      signal: controller.signal,
      headers: { authorization: `Bearer ${config.key}`, "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify({
        model: config.model,
        reasoning_effort: "low",
        max_completion_tokens: 900,
        response_format: {
          type: "json_schema",
          json_schema: {
            name: "group_chat_line",
            strict: false,
            schema: {
              type: "object",
              properties: {
                text: { type: "string" },
                itemIds: { type: "array", items: { type: "string" } },
                eventIds: { type: "array", items: { type: "string" } },
                draft: {
                  type: "object",
                  properties: {
                    title: { type: "string" },
                    placeId: { type: "string" },
                    day: { type: "string" },
                    time: { type: "string" },
                    description: { type: "string" },
                  },
                },
              },
              required: ["text"],
            },
          },
        },
        messages: [
          { role: "developer", content: INSTRUCTIONS },
          { role: "user", content: JSON.stringify({ task: kind, context, catalog: facts }) },
        ],
      }),
    });
    if (!response.ok) {
      console.error("muse-chat provider status", response.status);
      return { status: 502, body: { error: "provider" } };
    }
    const payload = (await response.json()) as { choices?: { message?: { content?: string } }[] };
    const parsed = JSON.parse(payload.choices?.[0]?.message?.content ?? "") as Record<string, unknown>;
    if (typeof parsed.text !== "string" || !parsed.text.trim()) return { status: 502, body: { error: "malformed" } };
    return {
      status: 200,
      body: {
        text: parsed.text.trim().slice(0, 400),
        source: "live",
        itemIds: kind === "supplies" || kind === "barter" ? ids(parsed.itemIds, itemIds) : [],
        eventIds: kind === "hangout" ? ids(parsed.eventIds, eventIds) : [],
        draft: kind === "create" ? cleanDraft(parsed.draft, venueIds) : null,
      },
    };
  } catch (error) {
    console.error("muse-chat failed", (error instanceof Error ? error.name : "error").slice(0, 60));
    return { status: 502, body: { error: "provider" } };
  } finally {
    clearTimeout(timer);
  }
}

/** Vercel Function entry (Web handler). */
export async function POST(request: Request): Promise<Response> {
  const key = process.env.MUSE_API_KEY || process.env.MODEL_API_KEY || "";
  const config = key ? { key, model: process.env.MUSE_MODEL || "muse-spark-1.3" } : null;
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    body = {};
  }
  const client = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  const result = await handleMuseChat(body, config, loadCatalog(), client);
  return Response.json(result.body, { status: result.status });
}
