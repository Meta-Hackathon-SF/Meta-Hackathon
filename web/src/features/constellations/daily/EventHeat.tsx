/*
 * "Where people like you are going" (D010): Facebook Events style list with a
 * heat level per event. Venues are from Adam's approved public venue list.
 * With `counts` (fixture: Synthetic players similar to you) it shows computed
 * heat; without, a labeled EXAMPLE. Code, not Muse, applies the threshold:
 * fewer than 3 similar people is never shown, and counts are bucketed.
 * "Interested" is private and remembered on this device; with "use my
 * activity" on it also becomes an Event signal.
 */
import { useState } from "react";
import { MapPin, Star } from "lucide-react";
import { HEAT_THRESHOLD, heatBucket } from "./synthetic";
import { readInterested, writeInterested } from "./activity";

export interface HeatEvent {
  id: string;
  title: string;
  venue: string;
  date: string; // ISO date
  time: string;
}

const EVENTS: HeatEvent[] = [
  { id: "ev-board-games", title: "Board game night", venue: "Library Commons", date: "2026-11-18", time: "7:00 PM" },
  { id: "ev-volleyball", title: "Pickup volleyball", venue: "Rec Center Courts", date: "2026-11-19", time: "6:30 PM" },
  { id: "ev-open-mic", title: "Open mic", venue: "Campus Cafe", date: "2026-11-20", time: "8:00 PM" },
  { id: "ev-film-club", title: "Film club", venue: "Main Quad", date: "2026-11-21", time: "7:30 PM" },
];
const EXAMPLE_COUNTS: Record<string, number> = { "ev-board-games": 11, "ev-volleyball": 6, "ev-open-mic": 3, "ev-film-club": 2 };

export default function EventHeat({
  counts,
  label,
  onInterestChange,
}: {
  counts?: Record<string, number> | null;
  label?: string;
  onInterestChange?: () => void;
}) {
  const [interested, setInterested] = useState<Set<string>>(() => new Set(readInterested()));
  const real = Boolean(counts);
  const source = counts ?? EXAMPLE_COUNTS;
  const shown = EVENTS.map((event) => ({ event, n: source[event.id] ?? 0, heat: heatBucket(source[event.id] ?? 0) }))
    .filter((row): row is { event: HeatEvent; n: number; heat: NonNullable<ReturnType<typeof heatBucket>> } => row.heat !== null)
    .sort((a, b) => b.n - a.n);

  return (
    <section className="card cst-panel" aria-labelledby="cst-heat-title" data-testid="cst-heat">
      <header className="cst-panel-head">
        <div>
          <h2 id="cst-heat-title">Where people like you are going</h2>
          <p className="muted">More people like you means a better chance of clicking with someone</p>
        </div>
        <span className="cst-label cst-label-warn">{real ? (label ?? "Synthetic players") : "Example"}</span>
      </header>
      {shown.length === 0 ? (
        <p className="cst-panel-note muted" data-testid="cst-heat-empty">
          No event has {HEAT_THRESHOLD} or more people like you yet. Answer a few more days.
        </p>
      ) : (
        <ul className="cst-heat-list">
          {shown.map(({ event, heat }) => {
            const d = new Date(`${event.date}T12:00:00Z`);
            const on = interested.has(event.id);
            return (
              <li key={event.id} className={`cst-heat-row is-heat-${heat.level}`} data-testid="cst-heat-row">
                <span className="cst-date-badge" aria-hidden="true">
                  <small>{d.toLocaleDateString(undefined, { month: "short", timeZone: "UTC" })}</small>
                  <strong>{d.getUTCDate()}</strong>
                </span>
                <span className="cst-heat-main">
                  <strong>{event.title}</strong>
                  <small className="muted">
                    {d.toLocaleDateString(undefined, { weekday: "short", timeZone: "UTC" })} · {event.time} ·{" "}
                    <span className="cst-venue">
                      <MapPin size={11} aria-hidden="true" /> {event.venue}
                    </span>
                  </small>
                  <span className="cst-heat-meter">
                    <span className="cst-heat-cells" aria-hidden="true">
                      {[1, 2, 3].map((n) => (
                        <i key={n} className={n <= heat.level ? "is-on" : undefined} />
                      ))}
                    </span>
                    <span>{heat.label}</span>
                  </span>
                </span>
                <button
                  type="button"
                  className={on ? "button-primary cst-interested" : "button-secondary cst-interested"}
                  aria-pressed={on}
                  onClick={() => {
                    const next = new Set(interested);
                    if (next.has(event.id)) next.delete(event.id);
                    else next.add(event.id);
                    setInterested(next);
                    writeInterested([...next]);
                    onInterestChange?.();
                  }}
                >
                  <Star size={15} aria-hidden="true" fill={on ? "currentColor" : "none"} /> Interested
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p className="cst-panel-note muted">
        Events with fewer than {HEAT_THRESHOLD} people like you are never shown. Nobody sees that you're interested.
      </p>
    </section>
  );
}
