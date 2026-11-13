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

const STORE_KEY = "cst-fixture-v1";
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
  guess: number | null;
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
  return { cycle: null, answers: [], guess: null, followUps: {}, seq: 0 };
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
    async myGuess(cycleId) {
      cycleOf(cycleId);
      return state.guess;
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
    async guess(cycleId, percent) {
      await wait();
      openCycle(cycleId);
      if (!Number.isInteger(percent) || percent < 0 || percent > 100)
        fail("INVALID_INPUT", "Request does not match the API requirements.");
      state.guess = percent;
      save();
      return { cycleId, playerId: PLAYER, percent };
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
        guess: null,
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
      state = { ...state, cycle: { ...cycle, status: "open", currentDay: 1 }, answers: [], guess: null, followUps: {} };
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
    clearLocalData() {
      state = { ...state, answers: [], guess: null, followUps: {} };
      save();
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
