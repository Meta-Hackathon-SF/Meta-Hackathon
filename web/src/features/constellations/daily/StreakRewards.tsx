import { Award, CalendarCheck, Flame, Sparkle } from "lucide-react";
import type { CSSProperties } from "react";
import type { DailyAnswer, Streak } from "./client";
import { computeRewards, nextReward, type RewardId } from "./rewards";

const ICONS: Record<RewardId, typeof Award> = {
  "first-light": Sparkle,
  "three-in-a-row": Flame,
  "every-day": CalendarCheck,
  "perfect-week": Award,
};

/** Badges for showing up. Cosmetic only; they never affect matching. */
export default function StreakRewards({ streak, answers }: { streak: Streak; answers: DailyAnswer[] }) {
  const rewards = computeRewards(streak, answers);
  const next = nextReward(rewards);
  const earned = rewards.filter((r) => r.earned).length;
  return (
    <section className="card cst-panel" aria-labelledby="cst-rewards-title" data-testid="cst-rewards">
      <header className="cst-panel-head">
        <div>
          <h2 id="cst-rewards-title">Rewards</h2>
          <p className="muted">
            {earned} of {rewards.length} earned
            {next ? ` · Next: ${next.title}, ${next.remaining.toLowerCase()}` : " · You earned every badge this week"}
          </p>
        </div>
        <span className="cst-label">Longest streak {Math.max(streak.longest, streak.current)}</span>
      </header>
      <ul className="cst-rewards">
        {rewards.map((r) => {
          const Icon = ICONS[r.id];
          return (
            <li key={r.id} className={r.earned ? "is-earned" : undefined} data-testid={`cst-reward-${r.id}`}>
              <span className="cst-badge" style={{ "--cst-progress": `${Math.round(r.progress * 360)}deg` } as CSSProperties} aria-hidden="true">
                <span>
                  <Icon size={20} />
                </span>
              </span>
              <strong>{r.title}</strong>
              <small className="muted">{r.earned ? "Earned" : r.detail}</small>
              <span className="sr-only">{r.earned ? "Earned." : `Not earned yet: ${r.remaining}.`}</span>
            </li>
          );
        })}
      </ul>
      <p className="cst-panel-note muted">Streaks reward showing up, never what you share. Badges are just for you and never change who you're matched with.</p>
    </section>
  );
}
