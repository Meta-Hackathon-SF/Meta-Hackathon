import type { CurrentCycle, CycleDay, DailyAnswer } from "../client";
import { SKY_COLORS } from "./sky";

export const DAY_LONG = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const dayHex = (day: number) => SKY_COLORS[Math.min(5, Math.max(1, day)) - 1];

export type Screen =
  | "home"
  | "answer"
  | "followup"
  | "distress"
  | "daily"
  | "sky"
  | "forming"
  | "main"
  | "chat"
  | "revealed"
  | "events"
  | "invite"
  | "settings";

export const SCREENS: readonly Screen[] = ["home", "answer", "followup", "distress", "daily", "sky", "forming", "main", "chat", "revealed", "events", "invite", "settings"];
export const CANVAS_SCREENS: readonly Screen[] = ["daily", "sky", "forming", "main"];
export const DARK_SCREENS: readonly Screen[] = [...CANVAS_SCREENS, "chat", "revealed"];

export interface WeekModel {
  /** 1-5 question days, 6 = Saturday (locked/forming), 7 = Sunday (revealed), 8 = week over. */
  day: number;
  /** Today's question day, or null when the week is locked. */
  today: CycleDay | null;
  answers: Map<number, DailyAnswer>;
  answered: Set<number>;
  catchUps: CycleDay[];
  streak: number;
}

export function weekModel(current: CurrentCycle, answers: DailyAnswer[]): WeekModel {
  const { cycle } = current;
  const day =
    cycle.status === "open" ? cycle.currentDay : cycle.status === "revealed" ? 7 : cycle.status === "closed" ? 8 : 6;
  const map = new Map(answers.map((a) => [a.day as number, a]));
  const catchUps =
    cycle.status === "open" ? ([1, 2, 3, 4] as CycleDay[]).filter((d) => d < cycle.currentDay && !map.has(d)) : [];
  return {
    day,
    today: cycle.status === "open" ? cycle.currentDay : null,
    answers: map,
    answered: new Set(map.keys()),
    catchUps,
    streak: current.streak.current,
  };
}
