/**
 * Muse helps the Sunday Messenger group plan a hangout. Facts come from the
 * approved venue list and the demo Marketplace. Muse may only phrase them.
 * A failed or off-catalog reply becomes the catalog line, labeled as such.
 */

export type MuseKind = "hangout" | "supplies" | "barter";

export interface MuseHelp {
  text: string;
  source: "live" | "catalog";
  link?: { href: string; label: string };
}

export const MUSE_FALLBACK: Record<MuseKind, string> = {
  hangout: "Board game night at Library Commons on Thursday at 7 PM. It's public, and it's easy to skip.",
  supplies: "The coffee set on Marketplace is $20 in Santa Cruz. That's a demo listing, not a purchase.",
  barter:
    "Ask Campus Cafe for a table, bring the coffee set, and split the check. Nothing is booked until the cafe agrees.",
};

/** Catalog lines answer the latest note using only the lines already in the chat. */
export function catalogReply(kind: MuseKind, notes: MuseNote[]): string {
  const earlier = notes
    .slice(0, -1)
    .map((note) => note.text.toLowerCase())
    .join(" ");
  const planned = earlier.includes("library commons") || earlier.includes("board game");
  if (kind === "hangout") return MUSE_FALLBACK.hangout;
  const latest = notes[notes.length - 1]?.text.toLowerCase() ?? "";
  const books = latest.includes("book") || latest.includes("class");
  if (kind === "supplies") {
    if (books) {
      return "Marketplace has a free textbook exchange for campus pickup. That's a demo listing, not a purchase.";
    }
    return planned
      ? "For the Library Commons night, the coffee set on Marketplace is $20 in Santa Cruz. That's a demo listing, not a purchase."
      : MUSE_FALLBACK.supplies;
  }
  return planned
    ? "Ask Campus Cafe for a table for the Library Commons night, bring the coffee set, and split the check. Nothing is booked until the cafe agrees."
    : MUSE_FALLBACK.barter;
}

const LINK: Partial<Record<MuseKind, { href: string; label: string }>> = {
  supplies: { href: "/marketplace", label: "See Marketplace" },
  barter: { href: "/marketplace", label: "See the coffee set" },
};

/** A live line that claims Muse will do the errand, or that a booking or purchase already happened. */
function overclaims(text: string): boolean {
  const claim = text
    .replace(/\bnothing is booked\b/g, "")
    .replace(/\bnot booked\b/g, "")
    .replace(/\bnot a purchase\b/g, "")
    .replace(/\bnot purchased\b/g, "");
  return (
    /\b(i'll|i will|let me|i'm going to|i am going to)\b/.test(claim) ||
    /\bi can (bring|grab|get|buy|pick)\b/.test(claim) ||
    /\b(booked|reserved|confirmed|purchased|bought|ordered)\b/.test(claim) ||
    /\b(should|will|can) hold\b/.test(claim) ||
    /\bholding a table\b/.test(claim)
  );
}

function accepts(kind: MuseKind, text: string): boolean {
  if (text.length === 0 || text.length > 400) return false;
  const lower = text.toLowerCase().replaceAll("’", "'");
  if (overclaims(lower)) return false;
  if (kind === "hangout") {
    return (
      lower.includes("library commons") &&
      !lower.includes("coffee") &&
      !lower.includes("textbook") &&
      !lower.includes("cafe") &&
      !lower.includes("listing") &&
      !lower.includes("purchase") &&
      !lower.includes("marketplace")
    );
  }
  if (kind === "supplies") {
    const listed = lower.includes("coffee set") || lower.includes("textbook");
    const demo = lower.includes("not a purchase") || lower.includes("demo listing");
    return listed && demo;
  }
  return lower.includes("campus cafe") && /\bask\b/.test(lower) && lower.includes("nothing is booked");
}

export interface MuseNote {
  sender: string;
  text: string;
}

/** Picks the kind of help from what was written. Code decides; Muse only phrases. */
export function inferKind(text: string): MuseKind {
  const t = text.toLowerCase();
  if (/\b(cafe|caf\u00e9|vendor|table|reserve|reservation|venue|book a|booking)\b/.test(t)) return "barter";
  if (/\b(buy|bring|need|supplies|snacks?|drinks?|coffee|books?|textbooks?|stuff|gear)\b/.test(t)) return "supplies";
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

export async function askMuse(kind: MuseKind, context: MuseNote[]): Promise<MuseHelp> {
  const link = LINK[kind];
  const notes = context
    .map((note) => ({ sender: note.sender.slice(0, 20), text: note.text.trim().slice(0, 200) }))
    .filter((note) => note.text)
    .slice(-6);
  if (!notes.length) return { text: catalogReply(kind, []), source: "catalog", link };
  try {
    const response = await fetch("/api/muse-chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      // Facts live on the server; the request carries only the task and anonymous lines.
      body: JSON.stringify({ kind, context: notes }),
    });
    if (response.ok) {
      const body: unknown = await response.json();
      const text = body && typeof body === "object" && "text" in body ? (body as { text: unknown }).text : "";
      if (typeof text === "string" && accepts(kind, text.trim())) {
        return { text: text.trim(), source: "live", link };
      }
    }
  } catch {
    /* Catalog line below. The key never lives in the browser. */
  }
  return { text: catalogReply(kind, notes), source: "catalog", link };
}
