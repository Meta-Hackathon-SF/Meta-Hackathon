/**
 * Muse helps the Sunday Messenger group plan. Facts come from the demo catalog
 * (src/data/catalog.json): Muse may only point at catalog items and events by
 * id, or propose an event draft on an approved venue. Code checks every reply;
 * a failed, off-catalog or overclaiming reply becomes a labeled catalog reply
 * chosen by code from the same catalog.
 */
import { BASE_EVENTS, ITEMS, WEEKDAYS, checkDraft, findItem, rank, type EventDraft } from "../../catalog/catalog";

export type MuseKind = "hangout" | "supplies" | "barter" | "create";

export interface MuseHelp {
  text: string;
  source: "live" | "catalog";
  itemIds: string[];
  eventIds: string[];
  draft: EventDraft | null;
}

export interface MuseNote {
  sender: string;
  text: string;
}

/** Picks the kind of help from what was written. Code decides; Muse only phrases. */
export function inferKind(text: string): MuseKind {
  const t = text.toLowerCase();
  if (/\b(create|organi[sz]e|host|set up|throw)\b/.test(t) || /\b(make|start|plan)\b.*\b(an? |our own |new )(event|meetup|hangout)\b/.test(t)) return "create";
  if (/\b(cafe|café|vendor|reserve|reservation|book a|booking|a table)\b/.test(t)) return "barter";
  if (/\b(buy|bring|need|supplies|snacks?|drinks?|coffee|books?|textbooks?|stuff|gear|marketplace|speaker|tent)\b/.test(t)) return "supplies";
  return "hangout";
}

/** Real names never reach Muse: other members become "Member 1..", you become "You". */
export function anonymize(context: { sender: string; text: string; mine: boolean; fromMuse: boolean }[]): MuseNote[] {
  const labels = new Map<string, string>();
  return context.map((note) => {
    if (note.fromMuse) return { sender: "Muse", text: note.text };
    if (note.mine) return { sender: "You", text: note.text };
    if (!labels.has(note.sender)) labels.set(note.sender, `Member ${Math.min(9, labels.size + 1)}`);
    return { sender: labels.get(note.sender)!, text: note.text };
  });
}

// ---------------------------------------------------------------- code-only fallback (no Muse)
const VENUE_HINTS: [RegExp, string][] = [
  [/\b(cafe|coffee|open mic|music)\b/, "v-cafe"],
  [/\b(food|dinner|lunch|eat|cook|dumpling)\b/, "v-dining-north"],
  [/\b(sport|volleyball|basketball|game of|ball|run|gym)\b/, "v-rec"],
  [/\b(movie|film|picnic|outside|outdoor|walk|sun)\b/, "v-quad"],
];

function draftFrom(notes: MuseNote[]): EventDraft {
  const latest = notes[notes.length - 1]?.text ?? "";
  const t = latest.toLowerCase();
  const placeId = VENUE_HINTS.find(([re]) => re.test(t))?.[1] ?? "v-library-commons";
  const day = WEEKDAYS.find((d) => t.includes(d.toLowerCase())) ?? "Thursday";
  const m = /\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/.exec(t);
  let hour = 19;
  if (m) hour = (Number(m[1]) % 12) + (m[3] === "pm" ? 12 : 0);
  hour = Math.min(22, Math.max(8, hour));
  const what = /\b(?:create|make|set up|organi[sz]e|host|start|throw)\s+(?:an?\s+|our\s+|the\s+)?([a-z][a-z\s-]{2,40}?)(?:\s+(?:on|at|this|next|for|@muse)\b|[.,!?]|$)/.exec(t)?.[1]?.trim();
  const title = what && what.length >= 3 ? what.replace(/\b\w/g, (c) => c.toUpperCase()) : "Group hangout";
  return checkDraft({ title, placeId, day, time: `${String(hour).padStart(2, "0")}:00`, description: "Planned in Messenger with Muse." })!;
}

/** Catalog reply chosen by code from the chat, used whenever Muse is unavailable or its reply is rejected. */
export function catalogReply(kind: MuseKind, notes: MuseNote[]): MuseHelp {
  const text = notes.map((n) => n.text).join(" ");
  const latest = notes[notes.length - 1]?.text ?? "";
  if (kind === "hangout") {
    const events = rank(BASE_EVENTS, `${latest} ${text}`);
    return {
      text: `${events[0].title} could work for the group. It's public, and it's easy to skip.`,
      source: "catalog",
      itemIds: [],
      eventIds: events.map((e) => e.eventId),
      draft: null,
    };
  }
  if (kind === "supplies") {
    const items = rank(ITEMS, latest.length > 12 ? latest : text);
    return {
      text: "These are on Marketplace. They're demo listings, not purchases.",
      source: "catalog",
      itemIds: items.map((i) => i.itemId),
      eventIds: [],
      draft: null,
    };
  }
  if (kind === "barter") {
    return {
      text: "Ask Campus Cafe for a table, bring the coffee set, and split the check. Nothing is booked until the cafe agrees.",
      source: "catalog",
      itemIds: ["mk-coffee-set"],
      eventIds: [],
      draft: null,
    };
  }
  return {
    text: "Here's a draft event. Tap Create to post it for the group.",
    source: "catalog",
    itemIds: [],
    eventIds: [],
    draft: draftFrom(notes),
  };
}

// ---------------------------------------------------------------- checks on live replies
/** A line that claims Muse will do the errand, or that a booking or purchase already happened. */
function overclaims(text: string): boolean {
  const claim = text
    .replace(/\bnothing is booked\b/g, "")
    .replace(/\bnot booked\b/g, "")
    .replace(/\bnot (a )?purchases?\b/g, "")
    .replace(/\bnot purchased\b/g, "");
  return (
    /\b(i'll|i will|let me|i'm going to|i am going to)\b/.test(claim) ||
    /\bi can (bring|grab|get|buy|pick|book|register)\b/.test(claim) ||
    /\b(booked|reserved|confirmed|purchased|bought|ordered|registered you|signed you up)\b/.test(claim) ||
    /\b(should|will|can) hold\b/.test(claim) ||
    /\bholding a table\b/.test(claim)
  );
}

const EVENT_IDS = new Set(BASE_EVENTS.map((e) => e.eventId));

function parseLive(kind: MuseKind, body: unknown): MuseHelp | null {
  if (!body || typeof body !== "object") return null;
  const b = body as Record<string, unknown>;
  const text = typeof b.text === "string" ? b.text.trim() : "";
  if (!text || text.length > 400 || overclaims(text.toLowerCase().replaceAll("’", "'"))) return null;
  const list = (v: unknown, ok: (id: string) => boolean) =>
    Array.isArray(v) ? [...new Set(v.filter((x): x is string => typeof x === "string" && ok(x)))].slice(0, 2) : [];
  const itemIds = list(b.itemIds, (id) => findItem(id) !== null);
  const eventIds = list(b.eventIds, (id) => EVENT_IDS.has(id));
  const draft = kind === "create" ? checkDraft(b.draft) : null;
  if (kind === "hangout" && !eventIds.length) return null;
  if (kind === "supplies" && !itemIds.length) return null;
  if (kind === "barter" && !(text.toLowerCase().includes("campus cafe") && text.toLowerCase().includes("nothing is booked"))) return null;
  if (kind === "create" && !draft) return null;
  return {
    text,
    source: "live",
    itemIds: kind === "supplies" || kind === "barter" ? itemIds : [],
    eventIds: kind === "hangout" ? eventIds : [],
    draft,
  };
}

export async function askMuse(kind: MuseKind, context: MuseNote[]): Promise<MuseHelp> {
  const notes = context
    .map((note) => ({ sender: note.sender.slice(0, 20), text: note.text.trim().slice(0, 200) }))
    .filter((note) => note.text)
    .slice(-6);
  if (!notes.length) return catalogReply(kind, []);
  try {
    const response = await fetch("/api/muse-chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      // Facts live on the server; the request carries only the task and anonymous lines.
      body: JSON.stringify({ kind, context: notes }),
    });
    if (response.ok) {
      const live = parseLive(kind, await response.json());
      if (live) return live;
    }
  } catch {
    /* Catalog reply below. The key never lives in the browser. */
  }
  return catalogReply(kind, notes);
}
