/*
 * Streak rewards. Computed in code from the server's Streak and this week's
 * answers (isCatchUp is server-set). Streaks reward showing up, never disclosure. Rewards are cosmetic badges only: they
 * never change matching, weights or what anyone else can see.
 */
import type { DailyAnswer, Streak } from "./client";

export type RewardId = "first-light" | "three-in-a-row" | "every-day" | "perfect-week";

export interface Reward {
  id: RewardId;
  title: string;
  detail: string;
  earned: boolean;
  /** 0..1 progress toward the badge. */
  progress: number;
  /** What is left, shown only when not earned. */
  remaining: string;
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

export function computeRewards(streak: Pick<Streak, "current" | "longest">, answers: Pick<DailyAnswer, "day" | "isCatchUp">[]): Reward[] {
  const days = new Set(answers.map((a) => a.day)).size;
  const onDay = new Set(answers.filter((a) => !a.isCatchUp).map((a) => a.day)).size;
  const best = Math.max(streak.current, streak.longest);
  const clamp = (n: number) => Math.max(0, Math.min(1, n));
  return [
    {
      id: "first-light",
      title: "First light",
      detail: "Answer your first question this week",
      earned: days >= 1,
      progress: clamp(days),
      remaining: "Answer today's question",
    },
    {
      id: "three-in-a-row",
      title: "Three in a row",
      detail: "Answer 3 question days in a row, on the day",
      earned: best >= 3,
      progress: clamp(best / 3),
      remaining: `${plural(3 - best, "more day")} in a row`,
    },
    {
      id: "every-day",
      title: "Every day counts",
      detail: "Answer all 5 days, catch-ups included",
      earned: days >= 5,
      progress: clamp(days / 5),
      remaining: `${plural(5 - days, "more day")} this week`,
    },
    {
      id: "perfect-week",
      title: "Perfect week",
      detail: "Answer all 5 days on the day",
      earned: onDay >= 5,
      progress: clamp(onDay / 5),
      remaining: `${plural(5 - onDay, "more on-day answer")}`,
    },
  ];
}

/** The next badge to work toward, or null when all are earned. */
export function nextReward(rewards: Reward[]): Reward | null {
  return rewards.find((r) => !r.earned) ?? null;
}
