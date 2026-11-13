/*
 * S5 daily constellation reveal (owner: Will; data from Rishi's placement).
 * Right after answering: the constellations you joined that day, unnamed, in
 * that day's color, plus how many people answered today (the only number).
 * Stars are week-randomized indices; nothing about another player is shown.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { Sparkles } from "lucide-react";
import { ClientError, type CycleClient, type CycleDay } from "./client";
import { DAY_NAMES } from "./useDaily";
import { DAY_COLORS, dayStyle, type DailyConstellation, type DailyConstellationsView } from "./v3";

const W = 600;
const H = 260;
const OPACITY = { bright: 1, mid: 0.72, faint: 0.45 } as const;

type Load = { state: "loading" } | { state: "ready"; view: DailyConstellationsView } | { state: "error"; message: string };

/** Lay every constellation around your star at the centre, fanned out so they don't overlap. */
function layout(view: DailyConstellationsView) {
  const cx = W / 2;
  const cy = H / 2;
  return view.constellations.map((c: DailyConstellation, i) => {
    const me = c.anchors.find((a) => a.index === view.myStarIndex) ?? c.anchors[0];
    const turn = (i / Math.max(1, view.constellations.length)) * Math.PI * 2 - Math.PI / 2;
    const cos = Math.cos(turn);
    const sin = Math.sin(turn);
    const others = c.anchors.filter((a) => a !== me);
    // Push each group outward along its own direction so lines read as separate shapes.
    const points = others.map((a) => {
      const dx = (a.x - me.x) * W * 0.75;
      const dy = (a.y - me.y) * H * 0.75;
      const rx = dx * cos - dy * sin + Math.cos(turn) * 120;
      const ry = dx * sin + dy * cos + Math.sin(turn) * 70;
      return { x: Math.min(W - 16, Math.max(16, cx + rx)), y: Math.min(H - 16, Math.max(16, cy + ry)) };
    });
    // Walk the stars by angle around you so the outline doesn't cross itself.
    points.sort((p, q) => Math.atan2(p.y - cy, p.x - cx) - Math.atan2(q.y - cy, q.x - cx));
    return { id: c.constellationId, brightness: c.brightness, points };
  });
}

/** Faint background sky, fixed per day so it doesn't jump between renders. */
function backdrop(day: number) {
  let seed = day * 9973;
  const next = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  return Array.from({ length: 70 }, () => ({ x: next() * W, y: next() * H, r: 0.4 + next() * 1.1, o: 0.15 + next() * 0.45 }));
}

export default function DailyReveal({
  client,
  cycleId,
  day,
  answerStamp,
}: {
  client: CycleClient;
  cycleId: string;
  day: CycleDay;
  /** Changes when your answer changes, so placement is refetched. */
  answerStamp: string;
}) {
  const v3 = client.v3;
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [tick, setTick] = useState(0);
  const request = useRef(0);

  useEffect(() => (v3 ? client.subscribe(() => setTick((t) => t + 1)) : undefined), [client, v3]);

  useEffect(() => {
    if (!v3) return;
    const id = ++request.current;
    const controller = new AbortController();
    v3.dailyConstellations(cycleId, day, controller.signal).then(
      (view) => id === request.current && setLoad({ state: "ready", view }),
      (err: unknown) => {
        if (id !== request.current || controller.signal.aborted) return;
        // NOT_FOUND = placement not there yet (or the route isn't mounted yet): still arriving.
        if (err instanceof ClientError && err.code === "NOT_FOUND")
          setLoad({ state: "ready", view: { day, colorId: DAY_COLORS[day].id, answeredToday: -1, placement: "pending", myStarIndex: 0, constellations: [] } });
        else setLoad({ state: "error", message: "Your stars aren't available right now. Your answer is saved." });
      },
    );
    return () => controller.abort();
  }, [v3, cycleId, day, answerStamp, tick]);

  const stars = useMemo(() => backdrop(day), [day]);
  if (!v3) return null;

  const color = DAY_COLORS[day];
  const view = load.state === "ready" ? load.view : null;
  const shapes = view ? layout(view) : [];
  const count = view?.constellations.length ?? 0;
  const arriving = load.state === "loading" || (view !== null && view.placement === "pending" && count === 0);
  const synthetic = client.mode === "fixture";

  return (
    <section className="card cst-reveal" style={dayStyle(day)} aria-labelledby="cst-reveal-title" data-testid="cst-reveal">
      <header className="cst-reveal-head">
        <div>
          <h2 id="cst-reveal-title">Your stars today</h2>
          <p className="muted">
            <span className="cst-day-chip">{DAY_NAMES[day - 1]}</span>
            {view && view.placement === "final" && <span className="cst-label cst-reveal-final">Day closed</span>}
          </p>
        </div>
        {view && view.answeredToday >= 0 && (
          <p className="cst-reveal-count" data-testid="cst-answered-today">
            <strong>{view.answeredToday.toLocaleString()}</strong>
            <span>{view.answeredToday === 1 ? "person answered today" : "people answered today"}</span>
          </p>
        )}
      </header>

      <div className="constellations cst-reveal-sky">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={
            arriving
              ? "Your stars are still arriving."
              : count === 0
                ? "No constellations yet today."
                : `You are in ${count} ${count === 1 ? "constellation" : "constellations"} today, shown in ${color.name.toLowerCase()}.`
          }
        >
          <g aria-hidden="true">
            {stars.map((s, i) => (
              <circle key={i} cx={s.x} cy={s.y} r={s.r} className="cst-reveal-bg-star" style={{ opacity: s.o }} />
            ))}
          </g>
          {shapes.map((shape, i) => (
            <g key={shape.id} className="cst-reveal-shape" style={{ opacity: OPACITY[shape.brightness], animationDelay: `${i * 220}ms` }}>
              {shape.points.map((p, k) => (
                <line key={`spoke-${k}`} x1={W / 2} y1={H / 2} x2={p.x} y2={p.y} className="cst-reveal-line is-spoke" pathLength={1} />
              ))}
              {shape.points.slice(1).map((p, k) => (
                <line
                  key={`edge-${k}`}
                  x1={shape.points[k].x}
                  y1={shape.points[k].y}
                  x2={p.x}
                  y2={p.y}
                  className="cst-reveal-line"
                  pathLength={1}
                />
              ))}
              {shape.points.map((p, k) => (
                <circle key={`star-${k}`} cx={p.x} cy={p.y} r={shape.brightness === "bright" ? 4.5 : 3.5} className="cst-reveal-star" />
              ))}
            </g>
          ))}
          <circle cx={W / 2} cy={H / 2} r={13} className="cst-reveal-me-ring" />
          <circle cx={W / 2} cy={H / 2} r={6.5} className="cst-reveal-me" />
          <text x={W / 2} y={H / 2 + 30} textAnchor="middle" className="cst-reveal-me-label">
            You
          </text>
        </svg>
        {arriving && (
          <p className="cst-reveal-overlay" role="status">
            <Sparkles size={16} aria-hidden="true" /> Your stars are still arriving
          </p>
        )}
      </div>

      <p className="cst-reveal-note">
        {load.state === "error"
          ? load.message
          : arriving
            ? "As people answer, you'll join the constellations closest to what you meant."
            : count === 0
              ? "Nobody close to your answer yet today. Check back as more people answer."
              : count === 1
                ? "You're in a constellation today. Each line is someone who answered close to what you meant. Who they are stays private."
                : "You're in several constellations today. Each line is someone who answered close to what you meant. Who they are stays private."}
      </p>
      {synthetic && (
        <p className="cst-reveal-labels">
          <span className="cst-label">Synthetic players</span>
          <span className="cst-label cst-label-warn">Fixture placement · no server</span>
        </p>
      )}
    </section>
  );
}
