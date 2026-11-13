import { BASE_EVENTS } from "../../../catalog/catalog";
/*
 * PREVIEW content for Space screens whose producers are still pending (contract
 * 3.0.0: week sky, formation, reveal chat, event signals). Every screen that uses
 * this file shows a "Preview" label. Nothing here is real player data.
 */
export const PREVIEW_DAY_COUNTS = [1912, 1648, 1390, 1275, 1203];

export const PREVIEW_MEMBERS = [
  { name: "Star 2", hex: "#F5B841" },
  { name: "Star 3", hex: "#2CC7C0" },
  { name: "Star 4", hex: "#F07196" },
  { name: "Star 5", hex: "#5BD27A" },
];

export const PREVIEW_MESSAGES: { member: number; text: string }[] = [
  { member: 1, text: "i really thought i was the only one who felt that way" },
  { member: 0, text: "same. tuesday's question got me" },
  { member: 3, text: "ok this is kind of nice honestly" },
];

export const PREVIEW_EVENTS = [
  { title: "Open mic", mon: "NOV", day: "20", sub: "Fri · 8 PM · Union", bucket: "6–10 of your people" },
  { title: "Study break", mon: "NOV", day: "19", sub: "Thu · 9 PM · Library", bucket: "3–5 of your people" },
  { title: "Intramural soccer", mon: "NOV", day: "21", sub: "Sat · 11 AM · Rec Center", bucket: null },
];

export const PREVIEW_INVITE = { title: "Board game night", mon: "NOV", day: "19", sub: "Thu · 7 PM · Memorial Union", threshold: 3 };

/** Client-side mirror of the chat contact-info guard, for the preview only. The server's M1 is authoritative. */
export const CONTACT_PATTERN = /(\d[\s.()-]?){7,}|@|https?:|www\.|\.(com|net|org|edu)\b/i;

export const SUPPORT_RESOURCES = [
  { name: "988 Suicide and Crisis Lifeline", sub: "Call or text 988, any time", href: "tel:988", action: "Call" },
  { name: "Crisis Text Line", sub: "Text HOME to 741741, any time", href: "sms:741741&body=HOME", action: "Text" },
];

/** PREVIEW: time people spent before answering, per weekday. Median seconds and % in <1m, 1–3m, 3–5m, 5m+. */
export const PREVIEW_THINK = [
  { median: 96, buckets: [34, 41, 17, 8] },
  { median: 164, buckets: [18, 40, 27, 15] },
  { median: 142, buckets: [22, 43, 24, 11] },
  { median: 201, buckets: [12, 35, 31, 22] },
  { median: 188, buckets: [15, 36, 29, 20] },
];

/** The demo invite: a catalog event (same data as the Events page and Muse). */
export const INVITE_EVENT = BASE_EVENTS.find((e) => e.eventId === "ev-board-games") ?? BASE_EVENTS[0];
