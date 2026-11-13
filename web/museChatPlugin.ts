/**
 * Dev-server helper for the Sunday Messenger group. Reads the gitignored Muse
 * key on the server and asks for one short chat line. The browser only sends
 * a task name and the catalog facts; it never sees the key.
 */
import fs from "node:fs";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";

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

function readKey(root: string): { key: string; model: string } | null {
  const file = path.resolve(root, "../server/providers/muse.env");
  let text = "";
  try {
    text = fs.readFileSync(file, "utf8");
  } catch {
    return null;
  }
  const values: Record<string, string> = {};
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const [name, rest] = line.split("=", 2);
    values[name.trim().replace(/^export\s+/, "")] = rest.trim().replace(/^["']|["']$/g, "");
  }
  const key = values.MUSE_API_KEY || values.MODEL_API_KEY || "";
  if (!key || key === "replace-me") return null;
  return { key, model: values.MUSE_MODEL || "muse-spark-1.3" };
}

function isKind(value: unknown): value is Kind {
  return value === "hangout" || value === "supplies" || value === "barter";
}

async function readBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(Buffer.from(chunk));
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
  } catch {
    return {};
  }
}

function send(res: ServerResponse, status: number, body: unknown) {
  res.statusCode = status;
  res.setHeader("content-type", "application/json");
  res.end(JSON.stringify(body));
}

export function museChatPlugin(): Plugin {
  return {
    name: "muse-chat",
    configureServer(server) {
      server.middlewares.use("/api/muse-chat", async (req, res) => {
        if (req.method !== "POST") {
          send(res, 405, { error: "POST only" });
          return;
        }
        const body = await readBody(req);
        const record = body && typeof body === "object" ? (body as { kind?: unknown; context?: unknown }) : {};
        const kind = record.kind;
        const context = Array.isArray(record.context)
          ? record.context
              .map((note) => {
                if (!note || typeof note !== "object") return null;
                const sender = "sender" in note && typeof note.sender === "string" ? note.sender.slice(0, 40) : "";
                const text = "text" in note && typeof note.text === "string" ? note.text.trim().slice(0, 200) : "";
                return sender && text ? { sender, text } : null;
              })
              .filter((note) => note !== null)
              .slice(-6)
          : [];
        if (!isKind(kind) || context.length === 0) {
          send(res, 400, { error: "needs a message" });
          return;
        }
        const config = readKey(server.config.root);
        if (!config) {
          send(res, 503, { error: "not_configured" });
          return;
        }
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 25_000);
        try {
          const response = await fetch("https://api.meta.ai/v1/chat/completions", {
            method: "POST",
            signal: controller.signal,
            headers: {
              authorization: `Bearer ${config.key}`,
              "content-type": "application/json",
              accept: "application/json",
            },
            body: JSON.stringify({
              model: config.model,
              reasoning_effort: "low",
              max_completion_tokens: 2000,
              response_format: {
                type: "json_schema",
                json_schema: {
                  name: "group_chat_line",
                  strict: false,
                  schema: {
                    type: "object",
                    properties: { text: { type: "string" } },
                    required: ["text"],
                  },
                },
              },
              messages: [
                {
                  role: "developer",
                  content:
                    "Suggest one next step. You do not bring, buy, book, or hold anything. Reply to the latest note only, in one or two sentences. Earlier notes are what words like 'it' refer to. Do not quote anyone. Use only the catalog facts. For a hangout, mention only Board game night at Library Commons on Thursday at 7 PM. Do not mention items, the cafe, Marketplace, a listing, or a purchase. For supplies, mention only the coffee set, unless the latest note asks about books, then mention only the textbook exchange. Say it is a demo listing, not a purchase. For a vendor, tell the group to ask Campus Cafe, and say nothing is booked until the cafe agrees. Never say I'll, I will, or let me. Never say a table is held or confirmed. No emoji. Use the venue, item, or vendor name exactly as given.",
                },
                { role: "user", content: JSON.stringify({ task: kind, context, facts: FACTS[kind] }) },
              ],
            }),
          });
          if (!response.ok) {
            console.error("muse-chat provider status", response.status);
            send(res, 502, { error: "provider" });
            return;
          }
          const payload = (await response.json()) as {
            choices?: { message?: { content?: string } }[];
          };
          const content = payload.choices?.[0]?.message?.content ?? "";
          const parsed = JSON.parse(content) as { text?: unknown };
          if (typeof parsed.text !== "string") {
            send(res, 502, { error: "malformed" });
            return;
          }
          send(res, 200, { text: parsed.text.trim(), source: "live" });
        } catch (error) {
          const message = error instanceof Error ? error.message : "error";
          console.error("muse-chat failed", message.slice(0, 180));
          send(res, 502, { error: "provider" });
        } finally {
          clearTimeout(timer);
        }
      });
    },
  };
}
