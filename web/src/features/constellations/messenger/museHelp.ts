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

const HANGOUT = {
  title: "Board game night",
  venue: "Library Commons",
  when: "Thursday at 7 PM",
};
const SUPPLIES = [
  { title: "Coffee set for your next study session", price: "$20", place: "Santa Cruz, CA" },
  { title: "Textbook exchange", price: "Free", place: "Campus pickup" },
];
const VENDOR = {
  name: "Campus Cafe",
  ask: "a table for the group",
  offer: "bring the coffee set from Marketplace and split the check",
};

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

export async function askMuse(kind: MuseKind, context: MuseNote[]): Promise<MuseHelp> {
  const link = LINK[kind];
  const notes = context
    .map((note) => ({ sender: note.sender.slice(0, 40), text: note.text.trim().slice(0, 200) }))
    .filter((note) => note.text)
    .slice(-6);
  if (!notes.length) return { text: catalogReply(kind, []), source: "catalog", link };
  try {
    const response = await fetch("/api/muse-chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        kind,
        context: notes,
        facts: kind === "hangout" ? HANGOUT : kind === "supplies" ? { items: SUPPLIES } : VENDOR,
      }),
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
