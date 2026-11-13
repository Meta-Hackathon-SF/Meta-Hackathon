/**
 * Dev-server mount for POST /api/muse-chat (fixture mode, no backend). Reads the
 * gitignored Muse key from server/providers/muse.env and uses the dev handler in
 * museChat.ts. The hosted app calls the backend route instead. The browser never
 * sees the key.
 */
import fs from "node:fs";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import catalog from "../server/cycle/data/catalog.json" with { type: "json" };
import { handleMuseChat, type MuseConfig } from "./museChat.ts";

function readKey(root: string): MuseConfig | null {
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
        const result = await handleMuseChat(await readBody(req), readKey(server.config.root), catalog);
        send(res, result.status, result.body);
      });
    },
  };
}
