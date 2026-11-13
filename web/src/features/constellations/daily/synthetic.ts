/*
 * FIXTURE ONLY: a synthetic constellation so the demo shows real D009/D010
 * behaviour without a server. Every person here is a labeled Synthetic player.
 * Same rules as server/matching/closeness.py: keyword closeness of answers plus
 * small capped boosts for shared Groups, Events and topics; bands by rank;
 * counts only; events under 3 similar people are hidden and counts bucketed.
 */
import type { Brightness, ConstellationContext } from "../../../../../contracts/protocol.ts";
import type { FixtureActivity } from "../privacy";

const STOP = new Set(
  `a about after again all already am an and any are as at be because been but by can could did do does doing don't
for from get gets got had has have having he her here hers him his how i i'm if in into is it it's its just like lot
me more most my no nor not now of off on one only or other our out over own really same she should so some such than
that the their them then there these they this those through to too under until up very was we were what when where
which while who why will with would you your yours honestly mostly usually`.split(/\s+/),
);
const stem = (t: string) => {
  for (const s of ["ing", "ed", "es", "s"]) if (t.length > s.length + 2 && t.endsWith(s)) return t.slice(0, -s.length);
  return t;
};
function vector(texts: string[]): Map<string, number> {
  const v = new Map<string, number>();
  for (const text of texts)
    for (const w of text.toLowerCase().match(/[a-z']+/g) ?? [])
      if (!STOP.has(w) && w.length > 2) v.set(stem(w), (v.get(stem(w)) ?? 0) + 1);
  return v;
}
function cosine(a: Map<string, number>, b: Map<string, number>): number {
  let dot = 0;
  for (const [k, x] of a) dot += x * (b.get(k) ?? 0);
  const n = (m: Map<string, number>) => Math.sqrt([...m.values()].reduce((s, x) => s + x * x, 0));
  return n(a) && n(b) ? dot / (n(a) * n(b)) : 0;
}
const overlap = (a: string[], b: string[]) => a.filter((x) => b.includes(x)).length;
function boost(a: FixtureActivity | null, b: FixtureActivity | null): number {
  if (!a || !b) return 0;
  return Math.min(
    0.3,
    Math.min(0.16, overlap(a.groupIds, b.groupIds) * 0.08) +
      Math.min(0.16, overlap(a.eventIds, b.eventIds) * 0.08) +
      Math.min(0.12, overlap(a.topics, b.topics) * 0.04),
  );
}

interface SyntheticPlayer {
  handle: string;
  color: string;
  answers: string[];
  activity: FixtureActivity;
}
const A = (groupIds: string[], eventIds: string[], topics: string[], profileId: string): FixtureActivity => ({
  profileId, groupIds, eventIds, friendIds: [], topics,
});
/** Four synthetic players in your constellation (labeled in the UI). */
export const SYNTHETIC_MEMBERS: SyntheticPlayer[] = [
  { handle: "Star 2", color: "#ffb86b", answers: ["The dining hall with my floor, loud but good", "Board games after class with friends"],
    activity: A(["g-hackathon-builders"], ["ev-board-games"], ["gaming", "food"], "fb-synthetic-2") },
  { handle: "Star 3", color: "#6be3c1", answers: ["Cooking dinner with my roommate most nights", "Breakfast in the dining hall before class"],
    activity: A(["g-xr-student-collective"], ["ev-open-mic"], ["music", "food"], "fb-synthetic-3") },
  { handle: "Star 4", color: "#c9a7ff", answers: ["Library commons, quiet table, coffee", "Board games at the library on Fridays"],
    activity: A([], ["ev-board-games"], ["study", "coffee"], "fb-synthetic-4") },
  { handle: "Star 5", color: "#7cc4ff", answers: ["Long hikes on the weekend, mostly alone", "Pickup volleyball at the rec center"],
    activity: A([], ["ev-volleyball"], ["outdoors", "sports"], "fb-synthetic-5") },
];

export interface SyntheticStar {
  handle: string;
  color: string;
  brightness: Brightness;
}
export interface SyntheticConstellation {
  stars: SyntheticStar[];
  context: ConstellationContext;
}

export function syntheticConstellation(myAnswers: string[], mine: FixtureActivity | null): SyntheticConstellation | null {
  if (!myAnswers.length) return null;
  const me = vector(myAnswers);
  const scored = SYNTHETIC_MEMBERS.map((p) => ({
    p,
    score: Math.min(1, cosine(me, vector(p.answers)) + boost(mine, p.activity)),
  })).sort((x, y) => y.score - x.score || x.p.handle.localeCompare(y.p.handle));
  const n = scored.length;
  const nBright = Math.max(1, Math.ceil(n / 3));
  const nFaint = Math.floor(n / 3);
  const bands: Brightness[] = [];
  scored.forEach((s, i) => {
    let band: Brightness = i < nBright ? "bright" : i >= n - nFaint ? "faint" : "mid";
    if (i && s.score === scored[i - 1].score) band = bands[i - 1];
    if (s.score < 0.05) band = "faint";
    bands.push(band);
  });
  const others = SYNTHETIC_MEMBERS.map((p) => p.activity);
  const context: ConstellationContext = mine
    ? {
        sharedGroupStars: others.filter((o) => overlap(o.groupIds, mine.groupIds) > 0).length,
        alreadyFriends: others.filter((o) => o.profileId && mine.friendIds.includes(o.profileId)).length,
        sameEventStars: others.filter((o) => overlap(o.eventIds, mine.eventIds) > 0).length,
      }
    : { sharedGroupStars: 0, alreadyFriends: 0, sameEventStars: 0 };
  return { stars: scored.map((s, i) => ({ handle: s.p.handle, color: s.p.color, brightness: bands[i] })), context };
}

/* ---- Event heat: a synthetic pool beyond your constellation ------------------------------ */
const POOL_EVENTS: { answers: string; events: string[] }[] = [
  ...Array.from({ length: 11 }, () => ({ answers: "board games dining hall friends floor", events: ["ev-board-games"] })),
  ...Array.from({ length: 6 }, () => ({ answers: "volleyball rec center outdoors hikes", events: ["ev-volleyball"] })),
  ...Array.from({ length: 3 }, () => ({ answers: "music open mic cafe singing dinner", events: ["ev-open-mic"] })),
  ...Array.from({ length: 2 }, () => ({ answers: "film club movies quad", events: ["ev-film-club"] })),
];

export const HEAT_THRESHOLD = 3;
export function heatBucket(n: number): { level: 1 | 2 | 3; label: string } | null {
  if (n < HEAT_THRESHOLD) return null;
  if (n >= 10) return { level: 3, label: "10+ people like you" };
  if (n >= 6) return { level: 2, label: "6–9 people like you" };
  return { level: 1, label: "3–5 people like you" };
}

/** eventId -> count of synthetic people similar to you (closeness >= 0.15) who are interested. */
export function syntheticEventCounts(myAnswers: string[], mine: FixtureActivity | null): Record<string, number> {
  const me = vector(myAnswers);
  const counts: Record<string, number> = {};
  for (const p of POOL_EVENTS) {
    const theirs = vector([p.answers]);
    const sharedEvent = mine ? overlap(mine.eventIds, p.events) * 0.08 : 0;
    if (cosine(me, theirs) + sharedEvent < 0.15) continue;
    for (const e of p.events) counts[e] = (counts[e] ?? 0) + 1;
  }
  return counts;
}
