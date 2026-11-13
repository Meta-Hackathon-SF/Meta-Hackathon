/*
 * Demo Marketplace and Events catalog (fictional). One JSON file feeds the
 * Marketplace and Events pages, Space, Messenger cards and the Muse route, so
 * every surface shows the same exact item or event.
 */
import data from "../../data/catalog.json";
import { photo } from "../../data/demo";

export interface Venue {
  placeId: string;
  name: string;
}
export interface MarketItem {
  itemId: string;
  title: string;
  price: string;
  place: string;
  image: string;
  seller: string;
  condition: string;
  category: string;
  tags: string[];
  description: string;
}
export interface CatalogEvent {
  eventId: string;
  title: string;
  placeId: string;
  start: string;
  when: string;
  image: string;
  host: string;
  going: number;
  capacity: number;
  tags: string[];
  description: string;
  /** Set on events a player created with Muse in this browser. */
  createdBy?: string;
}

export const VENUES: readonly Venue[] = data.venues;
export const ITEMS: readonly MarketItem[] = data.items;
export const BASE_EVENTS: readonly CatalogEvent[] = data.events;

export const itemImage = (item: Pick<MarketItem, "image">) => photo(item.image);
export const eventImage = (event: Pick<CatalogEvent, "image">) => photo(event.image);
export const venueName = (placeId: string) => VENUES.find((v) => v.placeId === placeId)?.name ?? "";
export const findItem = (itemId: string) => ITEMS.find((i) => i.itemId === itemId) ?? null;

const words = (text: string) => text.toLowerCase().match(/[a-z]+/g) ?? [];

/** Ranks catalog entries by overlap with the conversation. Code-only, used when Muse is unavailable. */
export function rank<T extends { tags: string[]; title: string }>(list: readonly T[], text: string, limit = 2): T[] {
  const w = new Set(words(text));
  const scored = list
    .map((entry, index) => {
      const terms = [...entry.tags, ...words(entry.title)];
      const score = terms.reduce((n, t) => n + (t.split(" ").every((p) => w.has(p) || w.has(`${p}s`)) ? 1 : 0), 0);
      return { entry, score, index };
    })
    .sort((a, b) => b.score - a.score || a.index - b.index);
  const hits = scored.filter((s) => s.score > 0);
  return (hits.length ? hits : scored).slice(0, limit).map((s) => s.entry);
}

// ---------------------------------------------------------------- event drafts (Muse proposes, code checks)
export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] as const;
export type Weekday = (typeof WEEKDAYS)[number];

export interface EventDraft {
  title: string;
  placeId: string;
  day: Weekday;
  /** 24-hour "HH:MM". */
  time: string;
  description: string;
}

const CONTACT = /(\d[\s.()-]?){7,}|@|https?:|www\.|\.(com|net|org|edu)\b/i;

/** Returns a clean draft, or null if anything is off. Venues come only from the approved list. */
export function checkDraft(value: unknown): EventDraft | null {
  if (!value || typeof value !== "object") return null;
  const d = value as Record<string, unknown>;
  const title = typeof d.title === "string" ? d.title.trim() : "";
  const description = typeof d.description === "string" ? d.description.trim() : "";
  const time = typeof d.time === "string" ? d.time.trim() : "";
  const day = WEEKDAYS.find((w) => w.toLowerCase() === String(d.day ?? "").trim().toLowerCase());
  const placeId = VENUES.some((v) => v.placeId === d.placeId) ? (d.placeId as string) : null;
  const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(time);
  const hour = m ? Number(m[1]) : -1;
  if (title.length < 3 || title.length > 60 || description.length > 160) return null;
  if (CONTACT.test(title) || CONTACT.test(description)) return null;
  if (!day || !placeId || hour < 8 || hour > 22) return null;
  return { title, placeId, day, time, description };
}

/** "19:00" -> "7 PM", "09:30" -> "9:30 AM". */
export function clock(time: string): string {
  const [h, m] = time.split(":").map(Number);
  const suffix = h >= 12 ? "PM" : "AM";
  const hour = h % 12 || 12;
  return m ? `${hour}:${String(m).padStart(2, "0")} ${suffix}` : `${hour} ${suffix}`;
}

export const draftWhen = (d: EventDraft) => `${d.day.slice(0, 3)} · ${clock(d.time)}`;
