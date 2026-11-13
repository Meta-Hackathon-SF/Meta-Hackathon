/**
 * POST /api/muse-chat: one short Muse line for the Sunday Messenger group.
 *
 * Runs as a Vercel Function on the deployed demo (key from the MUSE_API_KEY
 * environment variable) and inside the Vite dev server (key from the gitignored
 * server/providers/muse.env, see museChatPlugin.ts). Self-contained on purpose:
 * no relative imports, so the function bundles the same way in both places.
 *
 * The browser sends only a task kind and the last few chat lines, with members
 * already renamed to "Member 1..." and "You". Facts come from the fixed catalog
 * below, never from the request. The browser re-checks every reply and swaps in
 * a labeled catalog line if it overclaims (museHelp.ts).
 */

const FACTS = {
  hangout: { title: "Board game night", venue: "Library Commons", when: "Thursday at 7 PM" },
  supplies: {
    items: [
      { title: "Coffee set for your next study session", price: "$20", place: "Santa Cruz, CA" },
      { title: "Textbook exchange", price: "Free", place: "Campus pickup" },
    ],
  },
  barter: {
    name: "Campus Cafe",
    ask: "a table for the group",
    offer: "bring the coffee set from Marketplace and split the check",
  },
} as const;

type Kind = keyof typeof FACTS;

const INSTRUCTIONS =
  "Suggest one next step. You do not bring, buy, book, or hold anything. Reply to the latest note only, in one or two sentences. Earlier notes are what words like 'it' refer to. Do not quote anyone. Use only the catalog facts. For a hangout, mention only Board game night at Library Commons on Thursday at 7 PM. Do not mention items, the cafe, Marketplace, a listing, or a purchase. For supplies, mention only the coffee set, unless the latest note asks about books, then mention only the textbook exchange. Say it is a demo listing, not a purchase. For a vendor, tell the group to ask Campus Cafe, and say nothing is booked until the cafe agrees. Never say I'll, I will, or let me. Never say a table is held or confirmed. No emoji. Use the venue, item, or vendor name exactly as given.";

export interface MuseConfig {
  key: string;
  model: string;
}

export interface MuseResult {
  status: number;
  body: { text: string; source: "live" } | { error: string };
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
  return value === "hangout" || value === "supplies" || value === "barter";
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
export async function handleMuseChat(body: unknown, config: MuseConfig | null, client = "local"): Promise<MuseResult> {
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
        max_completion_tokens: 600,
        response_format: {
          type: "json_schema",
          json_schema: {
            name: "group_chat_line",
            strict: false,
            schema: { type: "object", properties: { text: { type: "string" } }, required: ["text"] },
          },
        },
        messages: [
          { role: "developer", content: INSTRUCTIONS },
          { role: "user", content: JSON.stringify({ task: kind, context, facts: FACTS[kind] }) },
        ],
      }),
    });
    if (!response.ok) {
      console.error("muse-chat provider status", response.status);
      return { status: 502, body: { error: "provider" } };
    }
    const payload = (await response.json()) as { choices?: { message?: { content?: string } }[] };
    const parsed = JSON.parse(payload.choices?.[0]?.message?.content ?? "") as { text?: unknown };
    if (typeof parsed.text !== "string" || !parsed.text.trim()) return { status: 502, body: { error: "malformed" } };
    return { status: 200, body: { text: parsed.text.trim().slice(0, 400), source: "live" } };
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
  const result = await handleMuseChat(body, config, client);
  return Response.json(result.body, { status: result.status });
}
