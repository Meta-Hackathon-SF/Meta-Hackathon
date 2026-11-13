/*
 * TEST-ONLY FIXTURE ADAPTER. No server, no Muse, no speech-to-text.
 *
 * Simulates the weekly-cycle rules in the browser so the daily and operator UI
 * can be built and tested before the API is composed. The UI shows "Fixture
 * mode" whenever this client is active. Results here prove UI behavior only.
 * State is kept in sessionStorage for this tab (synthetic data only).
 * Questions are copied from contracts/fixtures/week-sample.json + question-bank.json.
 */
import {
  ClientError,
  type AnswerResult,
  type CurrentCycle,
  type CycleClient,
  type CycleDay,
  type DailyAnswer,
  type DailyQuestion,
  type Streak,
  type WeeklyCycle,
} from "./client";
import type { EventNudge } from "../../../../../contracts/protocol.ts";
import { DAY_COLORS, type CustomEventProposal, type DailyConstellation, type DailyConstellationsView, type ProgressEvent, type V3Client, type WeekView } from "./v3";

const STORE_KEY = "cst-fixture-v2";
const PLAYER = "p-fixture-you";
const COMMUNITY = "community-demo";
const WEEK_START = "2026-11-09";

const QUESTIONS: [string, string, DailyQuestion["question"]["category"], string | null][] = [
  ["q-routine-meals", "Where did you eat most of your meals this week, and who was usually around?", "routine", "Was that by choice?"],
  ["q-joys-small-win", "What small thing made your day better recently?", "small_joys", "What made it stick with you?"],
  ["q-challenges-hard-part", "What's the hardest part of being new here that nobody talks about?", "challenges", null],
  ["q-interests-rabbit-hole", "What rabbit hole have you fallen into lately?", "interests", "What pulled you in?"],
  ["q-hopes-weekend", "If this weekend went perfectly, what would you be doing?", "hopes", "Who would be there?"],
];

interface State {
  cycle: WeeklyCycle | null;
  answers: DailyAnswer[];
  /** Days the operator closed (v3 day-close). */
  closedDays: number[];
  proposals: CustomEventProposal[];
  followUps: Record<string, { needsFollowup: boolean; question: string }>;
  seq: number;
}

function load(): State {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw) as State;
  } catch {
    /* storage unavailable: stay in memory */
  }
  return { cycle: null, answers: [], closedDays: [], proposals: seedProposals(), followUps: {}, seq: 0 };
}

function dateFor(day: number): string {
  const d = new Date(`${WEEK_START}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + day - 1);
  return d.toISOString().slice(0, 10);
}

function question(cycleId: string, day: CycleDay): DailyQuestion {
  const [questionId, text, category, followUpHint] = QUESTIONS[day - 1];
  return {
    cycleId,
    day,
    date: dateFor(day),
    question: {
      questionId,
      text,
      category,
      sensitivity: "low",
      signalTags: [],
      followUpHint,
      source: "curated",
      active: true,
    },
  };
}

const STEPS = ["open", "locked", "forming", "revealed", "closed"] as const;

// ---- v3 synthetic placement (TEST-ONLY) -----------------------------------------
// Deterministic stand-ins for Rishi's instant placement and day close. The other
// stars are Synthetic players; the UI labels them so. No answer text leaves this tab.
const SKY_SIZE = 10_000;
/** Synthetic players who answered each weekday before you. Shown as the only number. */
const SYNTHETIC_ANSWERED = [37, 42, 29, 51, 33];

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  return h >>> 0;
}
function rng(seed: number) {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}
/** Week-randomized: a new index every cycle, never a player id. */
const myStar = (cycleId: string) => hash(`star:${cycleId}`) % SKY_SIZE;

function placeDay(cycleId: string, day: number, answer: DailyAnswer): DailyConstellation[] {
  const rand = rng(hash(`${cycleId}:${day}:${answer.text.trim().toLowerCase()}`));
  const me = myStar(cycleId);
  const count = 1 + Math.floor(rand() * 3); // 1..3, MAX_DAILY_CONSTELLATIONS
  const bands = ["bright", "mid", "faint"] as const;
  return Array.from({ length: count }, (_, i) => {
    const size = 3 + Math.floor(rand() * 5); // 3..7 stars, you included
    const cx = 0.2 + rand() * 0.6;
    const cy = 0.25 + rand() * 0.5;
    const indices = [me];
    while (indices.length < size) {
      const index = Math.floor(rand() * SKY_SIZE);
      if (!indices.includes(index)) indices.push(index);
    }
    const anchors = indices.map((index, k) => {
      const angle = (k / size) * Math.PI * 2 + rand() * 0.6;
      const reach = k === 0 ? 0 : 0.12 + rand() * 0.16;
      return {
        index,
        x: Math.min(0.95, Math.max(0.05, cx + Math.cos(angle) * reach)),
        y: Math.min(0.92, Math.max(0.08, cy + Math.sin(angle) * reach * 0.8)),
      };
    });
    return { constellationId: `c-fixture-${day}-${i + 1}`, starIndices: indices, brightness: bands[i], anchors, memberCount: size, isFallback: true, museEvidence: null, sharedMeaning: "Quiet corners of campus where people feel most like themselves." };
  });
}

function seedProposals(): CustomEventProposal[] {
  const at = (days: number, hour: number) => {
    const d = new Date(Date.UTC(2026, 10, 14 + days, hour + 8));
    return d.toISOString().replace(/\.\d+Z$/, "Z");
  };
  const evidence = { model: "muse-spark-1.3", source: "replay" as const, generatedAt: "2026-11-13T07:00:00Z", latencyMs: 0, callType: "M7" as const };
  return [
    {
      proposalId: "proposal-fixture-1",
      clusterSize: 4,
      title: "Saturday dumpling night",
      why: "routine · meals · new here",
      placeId: "v-cafe",
      timeWindow: { startsAt: at(0, 18), endsAt: at(0, 20) },
      evidence,
      status: "pending",
    },
    {
      proposalId: "proposal-fixture-2",
      clusterSize: 3,
      title: "Sunday morning walk and coffee",
      why: "small joys · outdoors",
      placeId: "v-park",
      timeWindow: { startsAt: at(1, 10), endsAt: at(1, 12) },
      evidence,
      status: "pending",
    },
  ];
}

const FIXTURE_ROOM_ID = "room-orion";

/** Fixture nudge: a saved M7 result, always labeled "Replay of a saved cycle" by the card. */
async function replayNudge(roomId: string, signal?: AbortSignal): Promise<EventNudge> {
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, 250);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });
  const start = new Date();
  start.setDate(start.getDate() + 2);
  start.setHours(19, 0, 0, 0);
  const end = new Date(start.getTime() + 2 * 3600_000);
  return {
    nudgeId: `nudge-replay-${roomId}`,
    constellationId: "c-1",
    title: "Open mic night",
    placeId: "v-cafe",
    timeWindow: { start: start.toISOString(), end: end.toISOString() },
    why: "Low stakes and easy to leave early.",
    minAttendees: 3,
    evidence: { model: "muse-spark-1.3", source: "replay", generatedAt: new Date().toISOString(), latencyMs: 0, callType: "M7" },
  };
}

export function createFixtureClient(): CycleClient {
  let state = load();
  const listeners = new Set<() => void>();
  const save = () => {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
    listeners.forEach((listener) => listener());
  };
  const now = () => new Date().toISOString().replace(/\.\d+Z$/, "Z");
  const wait = () => new Promise((resolve) => setTimeout(resolve, 60));
  const fail = (code: ClientError["code"], message: string): never => {
    throw new ClientError(code, message);
  };
  const cycleOf = (cycleId: string): WeeklyCycle =>
    state.cycle && state.cycle.cycleId === cycleId ? state.cycle : fail("NOT_FOUND", "Resource not found.");
  const openCycle = (cycleId: string): WeeklyCycle => {
    const cycle = cycleOf(cycleId);
    return cycle.status === "open"
      ? cycle
      : fail("CYCLE_LOCKED", "This week is locked. Answers can no longer change.");
  };
  const find = (day: number) => state.answers.find((a) => a.day === day);
  const weight = (catchUp: boolean, followUp: boolean) =>
    Math.min(1.1, Math.round(((catchUp ? 0.6 : 1.0) + (followUp ? 0.1 : 0)) * 100) / 100);

  function streak(cycle: WeeklyCycle): Streak {
    let run = 0;
    let longest = 0;
    let last: string | null = null;
    const through = cycle.status === "open" ? cycle.currentDay : 5;
    for (let day = 1; day <= through; day++) {
      const answer = find(day);
      if (answer && !answer.isCatchUp) {
        run++;
        last = dateFor(day);
        longest = Math.max(longest, run);
      } else if (!answer && !(cycle.status === "open" && day === cycle.currentDay)) {
        run = 0;
      }
    }
    return { playerId: PLAYER, communityId: COMMUNITY, current: run, longest, lastOnDayDate: last };
  }

  function view(cycle: WeeklyCycle): CurrentCycle {
    const missed: CycleDay[] = [];
    if (cycle.status === "open")
      for (let day = 1; day < cycle.currentDay; day++) if (!find(day)) missed.push(day as CycleDay);
    return {
      cycle,
      question: cycle.status === "open" ? question(cycle.cycleId, cycle.currentDay) : null,
      streak: streak(cycle),
      catchUp: { cycleId: cycle.cycleId, missedDays: missed, closesAt: cycle.locksAt },
    };
  }

  function checkText(text: string): string {
    if (typeof text !== "string" || !text.trim() || text.length > 400)
      fail("INVALID_INPUT", "Request does not match the API requirements.");
    return text;
  }
  // Fixture stand-in for the M1 safety screen: only the synthetic marker is flagged.
  const flagged = (text: string) => text.includes("SYNTHETIC SAFETY TEST");

  function v3(): V3Client {
    const answeredToday = (cycle: WeeklyCycle, day: number) =>
      cycle.status === "open" && day === cycle.currentDay
        ? SYNTHETIC_ANSWERED[day - 1] + (find(day) && !flagged(find(day)!.text) ? 1 : 0)
        : 0;
    const placed = (cycleId: string, day: number) => {
      const answer = find(day);
      return answer && !flagged(answer.text) ? placeDay(cycleId, day, answer) : [];
    };
    return {
      async dailyConstellations(cycleId, day): Promise<DailyConstellationsView> {
        await wait();
        const cycle = cycleOf(cycleId);
        if (!find(day)) fail("NOT_FOUND", "Resource not found."); // only days you answered
        return {
          day,
          colorId: DAY_COLORS[day].id,
          answeredToday: answeredToday(cycle, day),
          placement: state.closedDays.includes(day) ? "final" : "ready",
          myStarIndex: myStar(cycleId),
          constellations: placed(cycleId, day),
        };
      },
      async sendQuietSignal() {
        return { sent: true, pulses: 1 }; // demo only: no other members exist in fixture mode
      },
      async week(cycleId): Promise<WeekView> {
        await wait();
        const cycle = cycleOf(cycleId);
        const through = cycle.status === "open" ? cycle.currentDay : 5;
        return {
          cycleId,
          days: ([1, 2, 3, 4, 5] as CycleDay[]).map((day) => {
            const answer = find(day);
            return {
              day,
              colorId: DAY_COLORS[day].id,
              released: day <= through,
              answered: !!answer,
              isCatchUp: !!answer?.isCatchUp,
              constellationCount: placed(cycleId, day).length,
            };
          }),
        };
      },
      // No fixture sky or main: the UI keeps its labeled preview until the real producers answer.
      async skyStars() {
        await wait();
        return fail("NOT_FOUND", "Resource not found.");
      },
      async skyMine() {
        await wait();
        return fail("NOT_FOUND", "Resource not found.");
      },
      async main() {
        await wait();
        return fail("NOT_FOUND", "Resource not found.");
      },
      // Honest stand-in: a labeled visualization, never presented as the matcher's trace.
      async formationProgress(): Promise<ProgressEvent> {
        await wait();
        return {
          phase: "done",
          step: 1,
          totalSteps: 1,
          attempts: [{ seq: 0, fromStarIndex: 0, toStarIndex: 1, outcome: "tried" }],
          source: "visualization",
          isVisualization: true,
        };
      },
      async closeDay(cycleId, day) {
        await wait();
        const cycle = cycleOf(cycleId);
        const through = cycle.status === "open" ? cycle.currentDay : 5;
        if (day > through) fail("INVALID_INPUT", "That day has not been released yet.");
        if (state.closedDays.includes(day)) fail("STALE_REVISION", "That day is already closed.");
        state.closedDays = [...state.closedDays, day].sort();
        save();
        return { jobId: `job-fixture-close-${day}` };
      },
      async customEvents() {
        await wait();
        return state.proposals.filter((p) => p.status === "pending");
      },
      async decideCustomEvent(proposalId, decision) {
        await wait();
        const proposal = state.proposals.find((p) => p.proposalId === proposalId) ?? fail("NOT_FOUND", "Resource not found.");
        if (proposal.status !== "pending") fail("STALE_REVISION", "Someone already decided this proposal.");
        const decided: CustomEventProposal = { ...proposal, status: decision === "approve" ? "approved" : "rejected" };
        state.proposals = state.proposals.map((p) => (p.proposalId === proposalId ? decided : p));
        save();
        return decided;
      },
    };
  }

  return {
    mode: "fixture",
    isOperator: true,
    async current() {
      await wait();
      return state.cycle ? view(state.cycle) : null;
    },
    async questions(cycleId) {
      const cycle = cycleOf(cycleId);
      const through = cycle.status === "open" ? cycle.currentDay : 5;
      return [1, 2, 3, 4, 5].filter((d) => d <= through).map((d) => question(cycleId, d as CycleDay));
    },
    async myAnswers(cycleId) {
      cycleOf(cycleId);
      return [...state.answers].sort((a, b) => a.day - b.day);
    },
    async submit(cycleId, body): Promise<AnswerResult> {
      await wait();
      const cycle = openCycle(cycleId);
      const text = checkText(body.text);
      if (body.day > cycle.currentDay) fail("INVALID_INPUT", "Request does not match the API requirements.");
      if (find(body.day)) fail("STALE_REVISION", "This was already answered. Refresh, then edit instead.");
      const isCatchUp = body.day < cycle.currentDay;
      const answer: DailyAnswer = {
        answerId: `answer-fixture-${++state.seq}`,
        cycleId,
        day: body.day,
        questionId: QUESTIONS[body.day - 1][0],
        playerId: PLAYER,
        text,
        source: body.source,
        isCatchUp,
        weight: weight(isCatchUp, false),
        followUpUsed: false,
        createdAt: now(),
        editedAt: null,
        deletedAt: null,
      };
      state.answers.push(answer);
      save();
      return { answer, supportCard: flagged(text) };
    },
    async edit(cycleId, day, body) {
      await wait();
      openCycle(cycleId);
      const text = checkText(body.text);
      const existing = find(day) ?? fail("NOT_FOUND", "Resource not found.");
      const issued = state.followUps[existing.answerId];
      const followUpUsed = existing.followUpUsed || !!(body.answersFollowUp && issued?.needsFollowup);
      const answer: DailyAnswer = {
        ...existing,
        text,
        followUpUsed,
        weight: weight(existing.isCatchUp, followUpUsed),
        editedAt: now(),
      };
      state.answers = state.answers.map((a) => (a.day === day ? answer : a));
      save();
      return { answer, supportCard: flagged(text) };
    },
    async remove(cycleId, day) {
      await wait();
      openCycle(cycleId);
      const existing = find(day) ?? fail("NOT_FOUND", "Resource not found.");
      state.answers = state.answers.filter((a) => a.day !== day);
      delete state.followUps[existing.answerId];
      save();
    },
    async followUp(cycleId, day) {
      await wait();
      openCycle(cycleId);
      const answer = find(day) ?? fail("NOT_FOUND", "Resource not found.");
      const issued = state.followUps[answer.answerId];
      if (issued) return issued;
      // Fixture stand-in for M2: short, unflagged answers get one canned follow-up.
      const needs = !flagged(answer.text) && !answer.followUpUsed && answer.text.trim().split(/\s+/).length < 6;
      const result = { needsFollowup: needs, question: needs ? "What made it feel that way this week?" : "" };
      state.followUps[answer.answerId] = result;
      save();
      return result;
    },
    async transcribe(audio) {
      await wait();
      if (!audio.size) fail("INVALID_INPUT", "The recording is empty.");
      return {
        transcript: "Synthetic transcript: mostly the dining hall, usually with headphones in.",
        mode: "fixture",
      };
    },
    async createCycle() {
      state = {
        cycle: {
          cycleId: `cycle-fixture-${Date.now().toString(36)}`,
          communityId: COMMUNITY,
          weekStart: WEEK_START,
          status: "open",
          currentDay: 1,
          locksAt: "2026-11-14T20:00:00Z",
          revealsAt: "2026-11-15T18:00:00Z",
          chatExpiresAt: "2026-11-21T20:00:00Z",
          demoTiming: true,
        },
        answers: [],
        closedDays: [],
        proposals: seedProposals(),
        followUps: {},
        seq: state.seq,
      };
      save();
      return state.cycle!;
    },
    async advance(cycleId) {
      const cycle = cycleOf(cycleId);
      if (cycle.status === "closed") fail("INVALID_INPUT", "Request does not match the API requirements.");
      state.cycle =
        cycle.status === "open" && cycle.currentDay < 5
          ? { ...cycle, currentDay: (cycle.currentDay + 1) as CycleDay }
          : { ...cycle, status: STEPS[STEPS.indexOf(cycle.status) + 1] };
      save();
      return state.cycle;
    },
    async topUp(cycleId) {
      openCycle(cycleId);
      // The real top-up writes server-side synthetic players; nothing is visible to this player.
      return { label: "Synthetic player", syntheticPlayers: 8, answersAdded: 0 };
    },
    async reset(cycleId) {
      const cycle = cycleOf(cycleId);
      state = { ...state, cycle: { ...cycle, status: "open", currentDay: 1 }, answers: [], closedDays: [], proposals: seedProposals(), followUps: {} };
      save();
      return state.cycle!;
    },
    async calls() {
      return [];
    },
    async reports() {
      return [];
    },
    async formationDebug() {
      return null; // formation runs on the server; the fixture adapter has none
    },
    async myRoomId(cycleId) {
      // The synthetic room from contracts/fixtures/chat-room.json, once the fixture week is revealed.
      const cycle = state.cycle;
      return cycle && cycle.cycleId === cycleId && cycle.status === "revealed" ? FIXTURE_ROOM_ID : null;
    },
    nudge: replayNudge,
    async reasoning() {
      return []; // fixture mode never calls Muse
    },
    v3: v3(),
    clearLocalData() {
      state = { ...state, answers: [], followUps: {} };
      save();
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
