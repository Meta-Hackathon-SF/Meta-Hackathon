/*
 * "Where people like you are going": a Facebook Events style list with a heat
 * level per event, drawn as an EXAMPLE. Real events come from Adam's approved
 * venue catalog (M7 nudges) and the "people like you" count from formation;
 * attending events as a signal is proposal D010. Code, not Muse, applies the
 * threshold: an event with fewer than 3 similar people is never shown, and
 * counts are bucketed so nobody can be singled out.
 */
import { useState } from "react";
import { MapPin, Star } from "lucide-react";

export const HEAT_THRESHOLD = 3;

export interface HeatEvent {
  id: string;
  title: string;
  venue: string;
  date: string; // ISO date
  time: string;
  similar: number; // people like you who are interested or going
}

// Venues come from Adam's approved public venue list (nudges/venues.ts), like real nudges.
const EXAMPLE_EVENTS: HeatEvent[] = [
  { id: "e1", title: "Board game night", venue: "Library Commons", date: "2026-11-18", time: "7:00 PM", similar: 11 },
  { id: "e2", title: "Pickup volleyball", venue: "Rec Center Courts", date: "2026-11-19", time: "6:30 PM", similar: 6 },
  { id: "e3", title: "Open mic", venue: "Campus Cafe", date: "2026-11-20", time: "8:00 PM", similar: 3 },
  { id: "e4", title: "Film club", venue: "Main Quad", date: "2026-11-21", time: "7:30 PM", similar: 2 }, // below threshold: hidden
];

/** Code-enforced: hide below the threshold, bucket the rest. */
export function heatOf(similar: number): { level: 1 | 2 | 3; label: string } | null {
  if (similar < HEAT_THRESHOLD) return null;
  if (similar >= 10) return { level: 3, label: "10+ people like you" };
  if (similar >= 6) return { level: 2, label: "6–9 people like you" };
  return { level: 1, label: "3–5 people like you" };
}

export default function EventHeat({ events = EXAMPLE_EVENTS }: { events?: HeatEvent[] }) {
  const [interested, setInterested] = useState<Set<string>>(new Set());
  const shown = events
    .map((event) => ({ event, heat: heatOf(event.similar) }))
    .filter((row): row is { event: HeatEvent; heat: NonNullable<ReturnType<typeof heatOf>> } => row.heat !== null)
    .sort((a, b) => b.event.similar - a.event.similar);

  return (
    <section className="card cst-panel" aria-labelledby="cst-heat-title" data-testid="cst-heat">
      <header className="cst-panel-head">
        <div>
          <h2 id="cst-heat-title">Where people like you are going</h2>
          <p className="muted">More people like you means a better chance of clicking with someone</p>
        </div>
        <span className="cst-label cst-label-warn">Example</span>
      </header>
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
                onClick={() =>
                  setInterested((prev) => {
                    const next = new Set(prev);
                    if (next.has(event.id)) next.delete(event.id);
                    else next.add(event.id);
                    return next;
                  })
                }
              >
                <Star size={15} aria-hidden="true" fill={on ? "currentColor" : "none"} /> Interested
              </button>
            </li>
          );
        })}
      </ul>
      <p className="cst-panel-note muted">
        Events with fewer than {HEAT_THRESHOLD} people like you are never shown. Nobody sees that you're interested.
      </p>
    </section>
  );
}
