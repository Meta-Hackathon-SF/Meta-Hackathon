/*
 * S6 your week (owner: Will). One row per weekday in that day's color, with a dot
 * for each of your own constellations that day. No names, no percentages.
 */
import { useEffect, useRef, useState } from "react";
import type { CycleClient } from "./client";
import { DAY_NAMES } from "./useDaily";
import { dayStyle, type WeekView } from "./v3";

function status(d: WeekView["days"][number]): string {
  if (!d.released) return "Not yet";
  if (!d.answered) return "Not answered";
  return d.isCatchUp ? "Caught up" : "Answered";
}

export default function WeekDays({ client, cycleId, stamp }: { client: CycleClient; cycleId: string; stamp: string }) {
  const v3 = client.v3;
  const [week, setWeek] = useState<WeekView | null>(null);
  const [failed, setFailed] = useState(false);
  const [tick, setTick] = useState(0);
  const request = useRef(0);

  useEffect(() => (v3 ? client.subscribe(() => setTick((t) => t + 1)) : undefined), [client, v3]);
  useEffect(() => {
    if (!v3) return;
    const id = ++request.current;
    const controller = new AbortController();
    v3.week(cycleId, controller.signal).then(
      (value) => {
        if (id !== request.current) return;
        setWeek(value);
        setFailed(false);
      },
      () => id === request.current && !controller.signal.aborted && setFailed(true),
    );
    return () => controller.abort();
  }, [v3, cycleId, stamp, tick]);

  if (!v3 || failed || !week) return null;
  return (
    <ol className="cst-weekdays" aria-label="Your constellations each day" data-testid="cst-weekdays">
      {week.days.map((d) => (
        <li key={d.day} className={`cst-weekday${d.answered ? " is-answered" : ""}${d.released ? "" : " is-locked"}`} style={dayStyle(d.day)}>
          <span className="cst-weekday-name">{DAY_NAMES[d.day - 1].slice(0, 3)}</span>
          <span className="cst-weekday-dots" aria-hidden="true">
            {d.constellationCount > 0
              ? Array.from({ length: d.constellationCount }, (_, i) => <i key={i} />)
              : <i className="is-empty" />}
          </span>
          <span className="cst-weekday-status">
            {status(d)}
            <span className="sr-only">
              {`, ${DAY_NAMES[d.day - 1]}: ${d.constellationCount} ${d.constellationCount === 1 ? "constellation" : "constellations"}`}
            </span>
          </span>
        </li>
      ))}
    </ol>
  );
}
